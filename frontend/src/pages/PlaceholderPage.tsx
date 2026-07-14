import { useLocation } from "react-router-dom";
export function PlaceholderPage() {
  const location = useLocation();
  return (
    <section>
      <h2>Yakında</h2>
      <p>{location.pathname} için temel ekran sonraki iterasyonda ayrıntılandırılacak.</p>
    </section>
  );
}
