// Darrel
// The incident form used for both a new incident and an edit: photo picker, undo/redo, and a review step.
import { useEffect, useMemo, useRef, useState } from "react";
import { ImagePlus, Redo2, Send, Undo2, X } from "lucide-react";
import { api } from "../api.js";

const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
const PHOTO_TYPES = ["image/png", "image/jpeg", "image/webp"];
const EMPTY_DRAFT = { description: "", location: "", reporter_role: "site_supervisor", injury: null, photo: null, removePhoto: false };

function draftFrom(incident) {
  if (!incident) return EMPTY_DRAFT;
  return { ...EMPTY_DRAFT, description: incident.description, location: incident.location,
           reporter_role: incident.reporter_role, injury: incident.injury };
}

// mode "new": starts empty. mode "edit": starts from `incident` and the review screen shows what changed.
// onSubmit(FormData) must throw to report a failure; nothing is sent until the user confirms on the review screen.
export default function IncidentForm({ mode = "new", incident = null, onSubmit, onCancel }) {
  const editing = mode === "edit";
  const initial = useMemo(() => draftFrom(incident), [incident]);
  const [draft, setDraft] = useState(initial);
  const [past, setPast] = useState([]);
  const [future, setFuture] = useState([]);
  const [step, setStep] = useState("form");
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const lastField = useRef(null);
  const fileInput = useRef(null);

  const existingPhoto = editing && incident.has_photo && !draft.removePhoto ? api.photoUrl(incident.id) : null;
  const newPreview = useMemo(() => (draft.photo ? URL.createObjectURL(draft.photo) : null), [draft.photo]);
  useEffect(() => () => newPreview && URL.revokeObjectURL(newPreview), [newPreview]);
  const shownPhoto = newPreview || existingPhoto;

  // Records a change. Typing in one box is one undo step; every other kind of change is its own step.
  function change(patch, field = null) {
    if (field === null || lastField.current !== field) {
      setPast([...past, draft]);
      setFuture([]);
    }
    lastField.current = field;
    setDraft({ ...draft, ...patch });
  }

  function undo() {
    if (!past.length) return;
    setFuture([draft, ...future]);
    setDraft(past[past.length - 1]);
    setPast(past.slice(0, -1));
    lastField.current = null;
  }

  function redo() {
    if (!future.length) return;
    setPast([...past, draft]);
    setDraft(future[0]);
    setFuture(future.slice(1));
    lastField.current = null;
  }

  // Quick checks in the browser; the server checks everything again (including the real image bytes).
  function choosePhoto(file) {
    if (!file) return;
    if (!PHOTO_TYPES.includes(file.type)) return setError("Photo must be a .png, .jpg, .jpeg or .webp file.");
    if (file.size > MAX_PHOTO_BYTES) return setError("The photo is larger than 5 MB. Please use a smaller photo.");
    setError(null);
    change({ photo: file });
  }

  function removePhoto() {
    if (fileInput.current) fileInput.current.value = "";
    change({ photo: null, removePhoto: Boolean(editing && incident.has_photo) });
  }

  function discard() {
    setDraft(initial);
    setPast([]);
    setFuture([]);
    setStep("form");
    setError(null);
    if (onCancel) onCancel();
  }

  function review(event) {
    event.preventDefault();
    if (draft.injury === null) return setError("Please say whether anyone was injured.");
    setError(null);
    setStep("review");
  }

  async function send(rerunAi = true) {
    const data = new FormData();
    ["description", "location", "reporter_role"].forEach((key) => data.append(key, draft[key]));
    data.append("injury", String(draft.injury));
    if (draft.photo) data.append("photo", draft.photo);
    else if (draft.removePhoto) data.append("remove_photo", "true");
    if (!rerunAi) data.append("rerun_ai", "false");
    setBusy(true);
    setError(null);
    try {
      await onSubmit(data);
      if (!editing) {
        setDraft(EMPTY_DRAFT);
        setPast([]);
        setFuture([]);
      }
      setStep("form");
    } catch (err) {
      setError(err.message);
      setStep("form");
    } finally {
      setBusy(false);
    }
  }

  const photoText = draft.photo ? `New photo: ${draft.photo.name}`
    : existingPhoto ? `Keep the current photo (${incident.photo_file})` : "No photo";
  const rows = [
    ["What happened", draft.description, editing && initial.description],
    ["Location", draft.location, editing && initial.location],
    ["Your role", draft.reporter_role, editing && initial.reporter_role],
    ["Anyone injured", draft.injury ? "Yes" : "No", editing && (initial.injury ? "Yes" : "No")],
    ["Photo", photoText, editing && (incident.has_photo ? "Current photo kept" : "No photo")],
  ];
  // Wording-only edits can skip the AI; a new injury answer or photo changes the analysis, so those need it.
  const needsAi = editing && (draft.injury !== initial.injury || Boolean(draft.photo) || draft.removePhoto);
  const changed = (label, now, was) => (label === "Photo" ? Boolean(draft.photo || draft.removePhoto) : was !== false && was !== now);

  if (step === "review") {
    return (
      <div className="card flat">
        <div className="card-title">
          <h3>{editing ? "Review your changes" : "Review before sending"}</h3>
          <span>Nothing is {editing ? "changed" : "sent to the AI or saved"} until you confirm</span>
        </div>
        {error && <div className="alert error">{error}</div>}
        <dl className="kv review">
          {rows.map(([label, now, was]) => (
            <div key={label} className="review-row">
              <dt>{label}</dt>
              <dd>{now}{changed(label, now, was) && <small className="was"> (was: {was})</small>}</dd>
            </div>
          ))}
        </dl>
        <div className="btn-row">
          <button className="btn primary" onClick={() => send(true)} disabled={busy}>
            {busy ? <><span className="spinner" /> AI is analysing...</> : <><Send size={15} /> {editing ? "Save and re-run the AI" : "Send"}</>}
          </button>
          {editing && (
            <button className="btn" onClick={() => send(false)} disabled={busy || needsAi}
                    title={needsAi ? "A new injury answer or photo needs the AI to run again" : "Keeps the earlier analysis"}>
              Save text only
            </button>
          )}
          <button className="btn" onClick={() => setStep("form")} disabled={busy}>Edit</button>
          <button className="btn danger" onClick={discard} disabled={busy}>Cancel</button>
        </div>
        {busy && <div className="alert info" style={{ marginTop: 14 }}>This can take up to a minute: the AI reads the description and photo, checks the weather and searches for similar incidents.</div>}
      </div>
    );
  }

  return (
    <form className={editing ? "card flat" : "card"} onSubmit={review}>
      <div className="card-title">
        <h3>{editing ? `Edit incident #${incident.id}` : "Log a new incident"}</h3>
        <span className="undo-bar">
          <button type="button" className="btn small" onClick={undo} disabled={!past.length} title="Undo"><Undo2 size={14} /> Undo</button>
          <button type="button" className="btn small" onClick={redo} disabled={!future.length} title="Redo"><Redo2 size={14} /> Redo</button>
        </span>
      </div>
      {error && <div className="alert error">{error}</div>}

      <div className="field">
        <label>What happened</label>
        <textarea className="input" rows={4} maxLength={500} required value={draft.description}
                  placeholder="e.g. Scaffold plank fell from level 4 and landed next to a worker without a helmet"
                  onChange={(e) => change({ description: e.target.value }, "description")} />
      </div>
      <div className="row">
        <div className="field">
          <label>Location</label>
          <input className="input" required maxLength={100} value={draft.location} placeholder="Site A - Block 3"
                 onChange={(e) => change({ location: e.target.value }, "location")} />
        </div>
        <div className="field">
          <label>Your role</label>
          <input className="input" required maxLength={40} value={draft.reporter_role}
                 onChange={(e) => change({ reporter_role: e.target.value }, "reporter_role")} />
        </div>
      </div>
      <div className="field">
        <label>Was anyone injured?</label>
        <div className="toggle">
          <button type="button" className={`btn ${draft.injury === true ? "selected" : ""}`} onClick={() => change({ injury: true })}>Yes</button>
          <button type="button" className={`btn ${draft.injury === false ? "selected" : ""}`} onClick={() => change({ injury: false })}>No</button>
        </div>
      </div>

      <div className="field">
        <label>Photo of the scene (optional)</label>
        {shownPhoto ? (
          <div className="preview">
            <img src={shownPhoto} alt="Selected" />
            <span className="preview-actions">
              <button type="button" className="btn" onClick={() => fileInput.current.click()}>Replace</button>
              <button type="button" className="btn" onClick={removePhoto}><X size={14} /> Remove</button>
            </span>
          </div>
        ) : (
          <div
            className={`dropzone ${dragging ? "drag" : ""}`}
            onClick={() => fileInput.current.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); choosePhoto(e.dataTransfer.files[0]); }}
          >
            <ImagePlus size={26} />
            Drag a photo here, or click to choose one
            <small>PNG, JPG or WEBP, max 5 MB. The AI checks it for hazards and safety gear.</small>
          </div>
        )}
        <input ref={fileInput} type="file" accept=".png,.jpg,.jpeg,.webp" hidden
               onChange={(e) => { choosePhoto(e.target.files[0]); e.target.value = ""; }} />
      </div>

      <div className="btn-row">
        <button className="btn primary" type="submit" style={{ flex: 1 }}>{editing ? "Review changes" : "Review and send"}</button>
        {editing && <button className="btn" type="button" onClick={discard}>Cancel</button>}
      </div>
    </form>
  );
}
