// Darrel
// The incident form used for both a new incident and an edit: photo picker, undo/redo, and a review step.
import { useEffect, useMemo, useRef, useState } from "react";
import { ImagePlus, Redo2, Send, Undo2, X } from "lucide-react";
import { api } from "../api.js";

const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
const PHOTO_TYPES = ["image/png", "image/jpeg", "image/webp"];
const EMPTY_DRAFT = { description: "", location: "", reporter_role: "site_supervisor", injury: null, photo: null, removePhoto: false };
