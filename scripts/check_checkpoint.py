"""Exercise a local checkpoint deployment with the documented demo accounts."""

import argparse
import http.cookiejar
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request


class ShopClient:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.cookies = http.cookiejar.CookieJar()
        self.token = None
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=context),
            urllib.request.HTTPCookieProcessor(self.cookies),
        )

    def request(self, path, data=None, method=None, raw=None, headers=None):
        headers = dict(headers or {})
        if path.startswith("/api/") and self.token:
            headers["Authorization"] = "Bearer " + self.token
        if raw is not None:
            body = raw
            headers["Content-Type"] = "application/json"
        elif data is not None:
            body = urllib.parse.urlencode(data).encode()
            headers.update({"Origin": self.base, "Referer": self.base + path})
            csrf = next((c.value for c in self.cookies if c.name == "csrftoken"), "")
            headers["X-CSRFToken"] = csrf
        else:
            body = None
        try:
            response = self.opener.open(
                urllib.request.Request(self.base + path, body, headers, method=method), timeout=20
            )
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.code, response.headers, response.read().decode(errors="replace")

    def api(self, path, data=None, method=None):
        status, headers, body = self.request(
            path, raw=json.dumps(data).encode() if data is not None else None, method=method
        )
        return status, headers, json.loads(body) if body else None

    def login(self, username, password):
        status, _, body = self.request("/accounts/login/")
        assert status == 200
        csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', body)[1]
        status, _, body = self.request(
            "/accounts/login/",
            {"csrfmiddlewaretoken": csrf, "username": username, "password": password},
        )
        assert status == 200 and "Выйти" in body, "HTML login failed"
        status, _, tokens = self.api(
            "/api/auth/token/", {"username": username, "password": password}
        )
        assert status == 200, tokens
        self.token = tokens["access"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://localhost")
    parser.add_argument("--expected-version", default="1.1.0")
    parser.add_argument("--password", default="DemoShop2026!")
    args = parser.parse_args()
    assert urllib.parse.urlparse(args.url).hostname in {"localhost", "127.0.0.1"}
    buyer, manager = ShopClient(args.url), ShopClient(args.url)
    status, headers, health = buyer.api("/healthz/")
    assert status == 200 and health["version"] == args.expected_version
    assert headers["X-Request-ID"]
    buyer.login("buyer_demo", args.password)
    manager.login("manager_demo", args.password)
    products = []
    for index in range(1, 6):
        status, _, product = buyer.api(f"/api/catalog/products/demo-shirt-{index}/")
        assert status == 200
        products.append(product)
    product = products[0]
    variant = next(v for v in product["variants"] if not v["is_default"] and v["stock"] > 0)
    print("PASS: version, request-id, HTML login/JWT, catalog variants and characteristics")
    for _ in range(2):
        assert buyer.api("/api/wishlist/", {"product": product["id"]})[0] == 201
    favorites = buyer.api("/api/wishlist/")[2]
    assert sum(row["product_id"] == product["id"] for row in favorites) == 1
    assert all(row["product_id"] != product["id"] for row in manager.api("/api/wishlist/")[2])
    for p in products[:4]:
        buyer.request(f"/compare/{p['id']}/", {"action": "remove"})
    for p in products[:4]:
        assert buyer.request(f"/compare/{p['id']}/", {"action": "add"})[0] == 200
    status, _, body = buyer.request(f"/compare/{products[4]['id']}/", {"action": "add"})
    assert status == 200 and "четырёх" in body and "table-warning" in body
    print("PASS: idempotent private wishlist, comparison limit and differences")
    status, _, body = buyer.request("/accounts/addresses/")
    csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', body)[1]
    status, _, body = buyer.request(
        "/accounts/addresses/",
        {
            "csrfmiddlewaretoken": csrf,
            "label": "Checkpoint",
            "city": "Новосибирск",
            "street": "Каменская",
            "house": "56",
            "is_primary": "on",
        },
    )
    assert status == 200
    address_id = int(re.search(r"/accounts/addresses/(\d+)/", body)[1])
    for item in buyer.api("/api/cart/")[2]["items"]:
        query = f"?variant={item['variant_id']}" if item["variant_id"] else ""
        buyer.api(f"/api/cart/items/{item['product_id']}/{query}", method="DELETE")
    assert (
        buyer.api(
            "/api/cart/items/", {"product": product["id"], "variant": variant["id"], "quantity": 1}
        )[0]
        == 200
    )
    checkout = {
        "full_name": "Checkpoint Buyer",
        "phone": "8 (913) 555-12-34",
        "email": "buyer_demo@example.test",
        "delivery_method": "courier",
        "address_book": address_id,
        "promo_code": "STUDENT10",
    }
    status, _, error = buyer.api("/api/orders/", {**checkout, "phone": "123"})
    assert status == 400 and "phone" in error
    status, order_headers, order = buyer.api("/api/orders/", checkout)
    assert status == 201, order
    assert order["phone"] == "+79135551234" and "Каменская" in order["address"]
    assert order["items"][0]["variant"] == variant["id"]
    assert float(order["discount"]) > 0 and order["delivery_cost"] == "500.00"
    assert buyer.api(f"/api/orders/{order['id']}/")[0] == 200
    print(
        f"PASS: order {order['id']}, address, variant, promo and phone; "
        f"request-id {order_headers['X-Request-ID']}"
    )
    for outcome in ("failed", "success"):
        status, _, body = buyer.request(f"/payments/gateway/{order['id']}/")
        assert status == 200
        csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', body)[1]
        status, _, body = buyer.request(
            f"/payments/gateway/{order['id']}/", {"csrfmiddlewaretoken": csrf, "outcome": outcome}
        )
        payload = json.loads(
            re.search(r'<script id="payment-body"[^>]*>(.*?)</script>', body, re.S)[1]
        )
        signature = json.loads(
            re.search(r'<script id="payment-signature"[^>]*>(.*?)</script>', body, re.S)[1]
        )
        assert (
            buyer.request(
                "/payments/webhook/", raw=payload.encode(), headers={"X-Payment-Signature": "wrong"}
            )[0]
            == 403
        )
        assert (
            buyer.request(
                "/payments/webhook/",
                raw=payload.encode(),
                headers={"X-Payment-Signature": signature},
            )[0]
            == 200
        )
        assert (
            buyer.request(
                "/payments/webhook/",
                raw=payload.encode(),
                headers={"X-Payment-Signature": signature},
            )[0]
            == 200
        )
    assert buyer.api(f"/api/orders/{order['id']}/")[2]["status"] == "paid"
    assert buyer.api(f"/api/orders/{order['id']}/cancel/", {})[0] == 400
    for state in ("confirmed", "shipped", "delivered"):
        assert manager.api(f"/api/orders/{order['id']}/status/", {"status": state})[0] == 200
    assert manager.api(f"/api/orders/{order['id']}/status/", {"status": "new"})[0] == 400
    print("PASS: payment decline/success, replay, bad signature, cancel guard, manager workflow")
    assert buyer.request("/reports/sales/")[0] == 403
    assert manager.request("/reports/sales/")[0] == 200
    assert "text/csv" in manager.request("/reports/sales/?format=csv")[1]["Content-Type"]
    if args.url.startswith("https:"):
        assert buyer.request("/api/docs/")[0] == 403
    assert manager.request("/api/docs/")[0] == 200
    assert manager.request("/admin/catalog/product/")[0] == 200
    print("PASS: report permission/CSV, staff Swagger and manager admin")
    print("PASS: checkpoint HTTP scenario completed; demo data and order are retained")


if __name__ == "__main__":
    main()
