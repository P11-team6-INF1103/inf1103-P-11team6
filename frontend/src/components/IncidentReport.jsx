// Darrel
import { api } from "../api.js";
import { SEVERITY_COLORS, formatDate } from "../labels.js";
import { OutcomePill } from "./Pills.jsx";

function Section({ title, children }) {
  return (
    <div className="report-section">
      <h4>{title}</h4>
      {children}
    </div>
  );
}

function BulletList({ items }) {
  return <ul>{items.map((item, i) => <li key={i}>{item}</li>)}</ul>;
}
