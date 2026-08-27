import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import { App } from "./App.tsx"
import { initializeTheme } from "./theme-core.ts"
import "./index.css"

initializeTheme()
createRoot(document.getElementById("root")!).render(<StrictMode><BrowserRouter><App /></BrowserRouter></StrictMode>)
