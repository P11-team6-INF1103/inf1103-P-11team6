// Darrel
import { SEVERITY_HEX } from "../site/colors.js";

// The hotspot glow and the incident pins, drawn on top of the plan inside the map's <svg>.
// heat is { elementId: count }; a pin is { id, sev, x, y, label } with x and y in plan metres.
export default function SiteMarks({ elements, pins, heat, heatOn, peak, unit, selectedId, onPick, show, hide }) {
  return (
    <>
        {heatOn && elements.filter((el) => heat[el.id]).map((el) => {
          const share = heat[el.id] / peak;
          const color = share > 0.75 ? "#f87171" : share > 0.5 ? "#fb923c" : share > 0.25 ? "#facc15" : "#a3e635";
          return (
            <g key={`heat-${el.id}`} style={{ pointerEvents: "none" }}>
              <rect x={el.x - unit} y={el.y - unit} width={el.w + unit * 2} height={el.d + unit * 2} rx={unit * 2}
                    fill={color} opacity={0.18 + 0.3 * share} filter="url(#site-blur)" />
              <circle cx={el.x + el.w - unit * 1.6} cy={el.y + unit * 1.6} r={unit * 1.7} fill={color} />
              <text x={el.x + el.w - unit * 1.6} y={el.y + unit * 2.3} fontSize={unit * 2} fontWeight="700" textAnchor="middle" fill="#0d1211">{heat[el.id]}</text>
            </g>
          );
        })}

        {pins.map((pin) => {
          const color = SEVERITY_HEX[pin.sev] || "#9db0ab";
          const picked = pin.id === selectedId;
          const s = unit * (picked ? 1.35 : 1);
          return (
            <g key={pin.id} transform={`translate(${pin.x} ${pin.y})`} style={{ cursor: "pointer" }}
               onClick={() => onPick?.(pin.id)} onMouseMove={(e) => show(pin.label, e)} onMouseLeave={hide}>
              {pin.sev === 5 && <circle r={s * 1.6} fill={color} opacity="0.5" className="site-pulse" />}
              {/* A drawing pin: the point sits on the spot, the round head above it holds the severity. */}
              <path d={`M 0 0 L ${-s * 0.9} ${-s * 2} A ${s * 1.35} ${s * 1.35} 0 1 1 ${s * 0.9} ${-s * 2} Z`} fill={color}
                    stroke={picked ? "#ffffff" : "#0d1211"} strokeWidth={s * (picked ? 0.2 : 0.14)} />
              <text y={-s * 1.55} fontSize={s * 1.7} fontWeight="700" textAnchor="middle" fill="#0d1211" style={{ pointerEvents: "none" }}>{pin.sev}</text>
            </g>
          );
        })}
    </>
  );
}
