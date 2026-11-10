// Lennart
// Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 900 },
});
