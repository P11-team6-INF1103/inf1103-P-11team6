// Darrel
import { Search } from "lucide-react";

export default function Header({ title, subtitle, search, onSearch }) {
  return (
    <header className="header">
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      <div className="header-right">
        <label className="search">
          <Search size={15} />
          <input placeholder="Search incidents..." value={search} onChange={(e) => onSearch(e.target.value)} />
        </label>
      </div>
    </header>
  );
}
