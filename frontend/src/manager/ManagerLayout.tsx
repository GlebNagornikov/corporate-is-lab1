import { NavLink, Outlet } from 'react-router'

export function ManagerLayout() {
  return <section>
    <nav className="nav" aria-label="Разделы сотрудника">
      <NavLink to="/manager/orders">Заказы</NavLink>
      <NavLink to="/manager/catalog">Каталог</NavLink>
      <NavLink to="/manager/reviews">Отзывы</NavLink>
      <NavLink to="/manager/promos">Промокоды</NavLink>
      <NavLink to="/manager/reports">Отчёты</NavLink>
    </nav>
    <Outlet />
  </section>
}

export function ManagerPlaceholder({ title }: { title: string }) {
  return <div><h1>{title}</h1><p>Раздел запланирован и появится на следующем этапе.</p></div>
}
