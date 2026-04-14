import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import AircraftIconDemo from "./AircraftIconDemo";
import "./styles.css";

const path = window.location.pathname.replace(/\/+$/, "");
const isAircraftIconDemo = path === "/aircraft-icons" || window.location.search.includes("demo=aircraft-icons");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {isAircraftIconDemo ? <AircraftIconDemo /> : <App />}
  </React.StrictMode>
);
