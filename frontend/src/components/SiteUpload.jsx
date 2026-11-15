// Ren Xiang
// Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { api } from "../api.js";

const MAX_SIDE = 2000;       // plan pictures are shrunk to this many pixels on the longest side
const MAX_BYTES = 4 * 1024 * 1024;

// Reads the picture's size and, if it is large, shrinks it to a JPEG so it stays under the server's 5 MB limit.
// Returns the file to upload and its shape (height / width).
async function preparePlan(file) {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise((resolve, reject) => {
      const el = new Image();
      el.onload = () => resolve(el);
      el.onerror = () => reject(new Error("That file could not be opened as an image."));
      el.src = url;
    });
    const aspect = img.naturalHeight / img.naturalWidth;
    const longest = Math.max(img.naturalWidth, img.naturalHeight);
    if (file.size <= MAX_BYTES && longest <= MAX_SIDE) return { file, aspect };
    const scale = MAX_SIDE / longest;
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.naturalWidth * Math.min(1, scale));
    canvas.height = Math.round(img.naturalHeight * Math.min(1, scale));
    canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
    if (!blob) throw new Error("The image could not be shrunk. Try a smaller file.");
    return { file: new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" }), aspect };
  } finally {
    URL.revokeObjectURL(url);
  }
}

// Step 1 of the site map: upload a picture of the site layout; the AI reads it and builds the map.
export default function SiteUpload({ onDraft }) {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [width, setWidth] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [dragging, setDragging] = useState(false);
  const imageInput = useRef(null);

  function pick(chosen) {
    if (!chosen) return;
    setError(null);
    setFile(chosen);
    setPreviewUrl((old) => { if (old) URL.revokeObjectURL(old); return URL.createObjectURL(chosen); });
  }

  async function generate() {
    setError(null);
    const metres = Number(width);
    if (!file) return setError("Choose a plan image first.");
    if (!(metres >= 20 && metres <= 2000)) return setError("Enter the real width of the picture in metres (20 to 2000).");
    setBusy(true);
    try {
      const { file: upload, aspect } = await preparePlan(file);
      const form = new FormData();
      form.append("plan", upload);
      form.append("site_width_m", String(metres));
      form.append("image_aspect", String(aspect));
      if (name.trim()) form.append("site_name", name.trim());
      const { plan, warnings } = await api.readSitePlan(form);
      onDraft(plan, warnings || [], "ai");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="site-setup">
      <div className="card">
        <div className="card-title"><h3>Upload your site layout</h3><span>The AI reads it and builds the site map</span></div>
        <div className="site-steps">
          <p><b>1.</b> A top-down plan, cropped to the site boundary (no title block or legend).</p>
          <p><b>2.</b> Label every structure and area on it.</p>
          <p><b>3.</b> Tell us the real width of the picture in metres.</p>
        </div>
        {!file ? (
          <div
            className={`dropzone ${dragging ? "drag" : ""}`}
            onClick={() => imageInput.current.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); pick(e.dataTransfer.files[0]); }}
          >
            <Upload size={22} />
            <div>Drag the plan here or click to choose</div>
            <small>PNG, JPG or WebP</small>
          </div>
        ) : (
          <div className="preview">
            <img src={previewUrl} alt="Plan to upload" />
            <button className="btn" onClick={() => { setFile(null); setPreviewUrl(null); }}>Remove</button>
          </div>
        )}
        <input ref={imageInput} type="file" accept=".png,.jpg,.jpeg,.webp,image/*" hidden onChange={(e) => pick(e.target.files[0])} />
        <div className="row" style={{ marginTop: 14 }}>
          <div className="field">
            <label htmlFor="site-width">Real width of the whole picture (metres)</label>
            <input id="site-width" className="input" type="number" min={20} max={2000} placeholder="e.g. 90" value={width} onChange={(e) => setWidth(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="site-name">Site name (optional)</label>
            <input id="site-name" className="input" placeholder="Tower Block C" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
        </div>
        {error && <div className="alert error">{error}</div>}
        <button className="btn primary" disabled={busy} onClick={generate}>
          {busy ? <><span className="spinner" /> Reading the plan...</> : "Generate site map"}
        </button>
      </div>

    </div>
  );
}
