// Sufi
// Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
import { Bar, BarChart, ResponsiveContainer } from "recharts";

// One of the four cards at the top: a number, a small bar chart of the last 14 days, and a trend line.
export default function StatCard({ label, value, icon: Icon, series, trend, trendBad }) {
  return (
    <div className="card stat">
      <div className="stat-top">
        {label}
        <span className="stat-icon"><Icon size={15} /></span>
      </div>
      <div className="stat-value">{value}</div>
      <div className="stat-bottom">
        <div className="trend"><b className={trendBad && !trend.startsWith("+0") ? "bad" : ""}>{trend}</b> last 7 days</div>
        <div style={{ width: 90, height: 40 }}>
          <ResponsiveContainer>
            <BarChart data={series}>
              <Bar dataKey="value" fill="#2fd59b" radius={[2, 2, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
