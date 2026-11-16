// Darrel
import { useEffect, useState } from "react";
import { Upload, Trash2 } from "lucide-react";
import { api } from "../api.js";

// The logged-in account: its name and profile picture, which can be changed or removed.
export default function Profile() {
  const [profile, setProfile] = useState(null);
  const [version, setVersion] = useState(0); // changes after an upload so the browser shows the new picture
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.profile().then(setProfile).catch((err) => setError(err.message));
  }, []);

  async function run(action) {
    setBusy(true);
    setError(null);
    try {
      setProfile(await action());
      setVersion((v) => v + 1);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function choose(event) {
    const file = event.target.files[0];
    event.target.value = ""; // so choosing the same file again still uploads it
    if (!file) return;
    const form = new FormData();
    form.append("photo", file);
    run(() => api.uploadProfilePhoto(form));
  }

  if (!profile) return error ? <div className="alert error">{error}</div> : <div className="empty">Loading your profile...</div>;

  return (
    <section className="card profile-card">
      <div className="card-title"><h3>Your account</h3></div>
      {error && <div className="alert error">{error}</div>}
      <div className="profile-row">
        {profile.has_photo
          ? <img className="profile-picture" src={api.profilePhotoUrl(version)} alt="Your profile picture" />
          : <div className="profile-picture profile-initial">{profile.username.charAt(0).toUpperCase()}</div>}
        <div>
          <div className="profile-name">{profile.username}</div>
          <div className="muted small">Logged in to the incident dashboard</div>
        </div>
      </div>
      <p className="muted small">Profile picture: .png, .jpg, .jpeg or .webp, up to 1 MB.</p>
      <div className="profile-actions">
        <label className={`btn primary ${busy ? "disabled" : ""}`}>
          <Upload size={14} /> {profile.has_photo ? "Change picture" : "Upload picture"}
          <input type="file" accept=".png,.jpg,.jpeg,.webp" hidden disabled={busy} onChange={choose} />
        </label>
        {profile.has_photo && (
          <button className="btn danger" disabled={busy} onClick={() => run(api.deleteProfilePhoto)}>
            <Trash2 size={14} /> Remove
          </button>
        )}
      </div>
    </section>
  );
}
