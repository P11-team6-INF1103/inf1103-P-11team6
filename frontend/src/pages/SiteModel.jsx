// Darrel
import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { placeIncidents, severityOf } from "../site/placement.js";
import { drawablePlan } from "../site/kinds.js";
import SiteUpload from "../components/SiteUpload.jsx";
import SiteReview from "../components/SiteReview.jsx";
import SiteMap from "../components/SiteMap.jsx";
import LocationsPanel from "../components/LocationsPanel.jsx";

const DAY_MS = 24 * 3600 * 1000;
