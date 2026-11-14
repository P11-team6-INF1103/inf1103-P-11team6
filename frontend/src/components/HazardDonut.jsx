// Lennart
// Donut of incidents by hazard type. The centre shows the top hazard's share and its name.
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { HAZARD_COLORS } from "../labels.js";

const CHART_HEIGHT = 190;
const INNER_RADIUS = 62;
const OUTER_RADIUS = 82;
// The label has to fit inside the hole, so it is narrower than the inner diameter.
const LABEL_WIDTH = INNER_RADIUS * 2 - 28;

const tooltipStyle = { background: "#1a2321", border: "1px solid #2a3633", borderRadius: 8, fontSize: 12 };

// hazards: [{ name, value }] sorted largest first. total: number of incidents.
export default function HazardDonut({ hazards, total }) {
  const top = hazards[0];
  const share = total && top ? Math.round((top.value / total) * 100) : 0;

  return (
    <div>
      <div style={{ height: CHART_HEIGHT, position: "relative" }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie data={hazards} dataKey="value" nameKey="name" innerRadius={INNER_RADIUS} outerRadius={OUTER_RADIUS}
                 paddingAngle={3} cornerRadius={6} stroke="none">
              {hazards.map((h, i) => <Cell key={h.name} fill={HAZARD_COLORS[i % HAZARD_COLORS.length]} />)}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} itemStyle={{ color: "#e9efed" }} />
          </PieChart>
        </ResponsiveContainer>
        <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", pointerEvents: "none" }}>
          <div style={{ textAlign: "center", width: LABEL_WIDTH }}>
            <div style={{ fontSize: 24, lineHeight: 1.1 }}>{share}%</div>
            <div style={{
              color: "var(--muted, #8a9a95)", fontSize: 11, lineHeight: 1.25, marginTop: 2,
              overflowWrap: "anywhere", textWrap: "balance",
              display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden",
            }} title={top ? top.name : undefined}>
              {top ? top.name : "No data"}
            </div>
          </div>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 8, marginTop: 10 }}>
        {hazards.slice(0, 4).map((h, i) => (
          <div key={h.name} style={{ border: "1px solid #2a3633", borderRadius: 8, padding: 8, fontSize: 12 }}>
            <i style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", marginRight: 6,
                        background: HAZARD_COLORS[i % HAZARD_COLORS.length] }} />{h.name}
            <div style={{ color: "var(--muted, #8a9a95)", marginTop: 2 }}>{h.value} incident{h.value === 1 ? "" : "s"}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
