"""Check the local lab stack over HTTPS; --purchase also creates a demo order."""

import argparse
import http.cookiejar
import json
import re
import secrets
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--purchase", action="store_true", help="Create a user and courier order")
    parser.add_argument("--expected-version", default="1.1.2", help="Expected deployed version")
    parser.add_argument("--phone", default="+79991234567", help="Phone submitted on checkout")
    parser.add_argument("--expected-phone", default="+79991234567", help="Expected saved phone")
    parser.add_argument("--check-invalid-phone", action="store_true", help="Reject phone 123 first")
    args = parser.parse_args()
    # This checker is deliberately restricted to the self-signed localhost lab.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    cookies = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=context),
        urllib.request.HTTPCookieProcessor(cookies),
        NoRedirect(),
    )

    def request(path, data=None, origin="https://localhost"):
        url = path if path.startswith("http") else "https://localhost" + path
        headers = {"Origin": origin, "Referer": "https://localhost/"} if data else {}
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        try:
            response = client.open(urllib.request.Request(url, body, headers), timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.code, response.headers, response.read().decode(errors="replace")

    def csrf(path):
        status, _, body = request(path)
        assert status == 200, (path, status)
        return re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', body)[1]

    status, headers, _ = request("http://localhost/")
    assert status == 301 and headers["Location"] == "https://localhost/"
    status, _, body = request("/healthz/")
    assert status == 200 and json.loads(body) == {"status": "ok", "version": args.expected_version}
    status, headers, body = request("/")
    assert status == 200 and "nginx" in headers["Server"]
    assert headers["X-Frame-Options"] == "DENY"
    assert "max-age=60" in headers["Strict-Transport-Security"]
    assert "djDebug" not in body
    status, headers, _ = request("/static/admin/css/base.css")
    assert status == 200 and "text/css" in headers["Content-Type"]
    token = csrf("/accounts/login/")
    status, _, _ = request(
        "/accounts/login/", {"csrfmiddlewaretoken": token}, origin="https://evil.example"
    )
    assert status == 403
    print("PASS: HTTP redirect, health/version, HTTPS headers, nginx CSS, foreign-origin CSRF")
    if not args.purchase:
        return

    suffix = secrets.token_hex(5)
    username = "lab7check_" + suffix
    email = username + "@example.test"
    password = secrets.token_urlsafe(24)
    status, _, body = request("/api/catalog/products/?in_stock=true")
    assert status == 200
    products = json.loads(body)
    products = products["results"] if isinstance(products, dict) else products
    product = next(item for item in products if item["stock"] > 0)
    variant = next(
        (
            item
            for item in product.get("variants", [])
            if item["is_active"] and not item["is_default"] and item["stock"] > 0
        ),
        None,
    )
    status, _, body = request("/product/" + product["slug"] + "/")
    assert status == 200, "Product detail must be available"
    image = re.search(r'src="(/media/[^"]+)"', body)
    assert image and request(image[1])[0] == 200, "nginx must serve product images"
    token = csrf("/accounts/signup/")
    status, _, _ = request(
        "/accounts/signup/",
        {
            "csrfmiddlewaretoken": token,
            "username": username,
            "email": email,
            "password1": password,
            "password2": password,
        },
    )
    assert status == 302, ("signup", status)
    token = csrf("/accounts/login/")
    status, _, _ = request(
        "/accounts/login/",
        {"csrfmiddlewaretoken": token, "username": username, "password": password},
    )
    assert status == 302, ("login", status)
    assert any(cookie.name == "sessionid" and cookie.secure for cookie in cookies)
    token = csrf("/product/" + product["slug"] + "/")
    status, _, _ = request(
        f"/cart/add/{product['id']}/",
        {"csrfmiddlewaretoken": token, "quantity": 1, "variant": variant["id"] if variant else ""},
    )
    assert status == 302, ("cart", status)
    token = csrf("/orders/checkout/")
    if args.check_invalid_phone:
        status, _, body = request(
            "/orders/checkout/",
            {
                "csrfmiddlewaretoken": token,
                "full_name": "Lab 7 HTTPS Check",
                "phone": "123",
                "email": email,
                "delivery_method": "courier",
                "address": "Local lab, test address",
            },
        )
        assert status == 200 and "id_phone_error" in body, "Invalid phone must show field error"
        assert "Введите российский номер телефона" in body
        token = csrf("/orders/checkout/")
        print("PASS: invalid phone rejected with field error; cart retained")
    status, headers, _ = request(
        "/orders/checkout/",
        {
            "csrfmiddlewaretoken": token,
            "full_name": "Lab 7 HTTPS Check",
            "phone": args.phone,
            "email": email,
            "delivery_method": "courier",
            "address": "Local lab, test address",
            "comment": "Automated lab 7 verification",
        },
    )
    assert status == 302 and re.fullmatch(r"/orders/\d+/", headers["Location"]), (
        "checkout",
        status,
        headers.get("Location"),
    )
    order_url = headers["Location"]
    assert request(order_url)[0] == 200
    status, _, body = request("/api" + order_url)
    assert status == 200 and json.loads(body)["phone"] == args.expected_phone
    print(f"PASS: saved order phone {args.expected_phone}")
    for _ in range(10):
        status, _, body = request("http://localhost:8026/api/v1/messages")
        assert status == 200
        if email in body:
            break
        time.sleep(1)
    else:
        raise AssertionError("Order email not found in production Mailpit")
    print(f"PASS: nginx media, signup, login, Secure session, cart, courier order {order_url}")
    print(f"PASS: order email delivered to Mailpit for {email}")


if __name__ == "__main__":
    main()
