import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const page = () => readFileSync(resolve("src/pages/index.astro"), "utf8");
const layout = () =>
  readFileSync(resolve("src/layouts/BaseLayout.astro"), "utf8");
const css = () => readFileSync(resolve("src/styles/global.css"), "utf8");
const frontendCss = () =>
  readFileSync(resolve("../frontend/src/index.css"), "utf8");

describe("public landing contract", () => {
  it("uses the course-evidenced navigation, copy, and configured public auth routes", () => {
    const html = page();
    for (const label of [
      "Experimentos",
      "Documentos",
      "Asistente",
      "Recorrido",
      "Ingresar",
    ])
      expect(html).toContain(label);
    for (const text of [
      "Espacio de Experimentos",
      "Registrá, consultá y explicá el trabajo de tus experimentos de IA.",
      "Crear espacio",
      "Ver cómo funciona",
      "Registrá",
      "Evolucioná",
      "Consultá",
      "Panorama del producto",
      "Modos del asistente",
      "Seguridad multi-tenant",
      "Empezá por el acceso",
      "Creá tu espacio o ingresá para trabajar sobre una base aislada por tenant.",
      "Aplicación educativa para experimentos, datos y conocimiento técnico.",
    ])
      expect(html).toContain(text);
    expect(html).toContain(
      'import.meta.env.PUBLIC_APP_URL ?? "http://localhost:5173"',
    );
    expect(html).toContain("${appUrl}/login");
    expect(html).toContain("${appUrl}/register");
    expect(html).not.toMatch(
      /Aprendizaje colaborativo|Iniciar sesión|Crear un espacio|Conocer el recorrido/i,
    );
    expect(html).toContain('class="nav-login-button"');
    expect(html).toContain('class="mobile-login-button"');
    expect(html.match(/Acceder al sistema/g)).toHaveLength(2);

    expect(css()).toMatch(
      /\.nav \.nav-login-button\s*\{[^}]*white-space:\s*nowrap[^}]*border-radius:\s*999px[^}]*padding:\s*\.5rem 1rem[^}]*height:\s*2\.35rem[^}]*background:\s*var\(--primary\)[^}]*color:\s*var\(--primary-foreground\)[^}]*font-size:\s*\.875rem[^}]*font-weight:\s*600/s,
    );
    expect(css()).toMatch(
      /\.mobile-login-button\s*\{[^}]*min-height:\s*2\.75rem[^}]*border-radius:\s*999px/s,
    );
  });

  it("keeps the mobile header controls tappable and exposes login only from its collapsed navigation", () => {
    const html = page();
    const styles = css();

    expect(html).toContain('class="mobile-menu"');
    expect(html).toContain('class="menu-icon" aria-hidden="true"');
    expect(html).toContain(
      '<a class="mobile-login-button" href={`${appUrl}/login`}>Acceder al sistema</a>',
    );
    expect(styles).toMatch(
      /@media\(max-width:560px\)\{[\s\S]*?\.nav-action \.nav-login-button\{display:none\}/,
    );
    expect(styles).toMatch(
      /\.mobile-menu summary\s*\{[^}]*width:2\.75rem[^}]*height:2\.75rem/s,
    );
    expect(styles).toMatch(/\.menu-icon\s*\{[^}]*display:grid[^}]*gap:/s);
    expect(styles).toMatch(/\.menu-icon span\s*\{[^}]*height:2px/s);
  });

  it("initializes a persisted system-aware theme before paint and exposes its accessible toggle state", () => {
    expect(layout()).toContain("localStorage.getItem(key)");
    expect(layout()).toContain("prefers-color-scheme: dark");
    expect(layout()).toContain(
      "document.documentElement.dataset.theme = theme",
    );
    expect(layout()).toContain(
      "document.documentElement.style.colorScheme = theme",
    );
    expect(page()).toContain("aria-pressed");
    expect(page()).toContain("data-theme-toggle");
    expect(page()).toContain("localStorage.setItem(key, theme)");
    expect(page()).toContain('control.setAttribute("aria-label"');
    expect(page()).toContain(
      'document.querySelectorAll("[data-theme-toggle]")',
    );
    expect(page()).toContain("toggles.forEach");
    expect(layout()).toContain(
      "try { return localStorage.getItem(key); } catch",
    );
    expect(page()).toContain("try { localStorage.setItem(key, theme); } catch");
    expect(page()).not.toContain("data-theme-toggle-mobile");
    expect(page().match(/data-theme-toggle(?=[\s>])/g)).toHaveLength(1);
    expect(page()).toContain(
      '<div class="nav nav-action"><button class="theme" type="button" aria-label="Activar tema oscuro" aria-pressed="false" data-theme-toggle>',
    );
    expect(page()).toContain(
      '<a class="mobile-login-button" href={`${appUrl}/login`}>Acceder al sistema</a>',
    );
    expect(page()).toContain("<script is:inline>const key");
    expect(page()).not.toContain("<script is:inline>{`");
  });

  it("reuses the supplied visual system with visibly distinct semantic light and dark palettes", () => {
    expect(css()).toContain('font-family: "Montserrat"');
    expect(css()).toContain("--brand-accent");
    expect(css()).toContain(':root[data-theme="dark"]');
    expect(css()).toContain("--background:");
    expect(css()).toContain("--card:");
    expect(css()).toContain(".section-shell");
    expect(css()).toContain(".section-container");
    expect(css()).toContain(".surface-card");
    expect(css()).toContain(".fade-in-section");
    for (const selector of [
      "body",
      ".header",
      ".surface-card",
      ".architecture-band",
      ".footer",
      ".button",
    ])
      expect(css()).toContain(selector);
    expect(layout()).toContain("montserrat-latin-400-600.woff2");
  });

  it("presents the evidenced product model, security boundaries, and current-versus-planned status", () => {
    const html = page();
    for (const anchor of [
      "#panorama",
      "#experimentos",
      "#datos",
      "#documentos",
      "#asistente",
      "#seguridad",
      "#estado",
      "#recorrido",
    ])
      expect(html).toContain(anchor);
    for (const text of [
      "contexto disperso de cada experimento",
      "datasets, modelos, ejecuciones, parámetros, resultados, métricas y procedencia",
      "modelos relacionales y documentales",
      "Bronze, Silver y Gold",
      "archivos fuente privados en MinIO",
      "chunks, embeddings, recuperación semántica y citas",
      "Documental",
      "Experimentos · Text-to-SQL de solo lectura",
      "Combinado / automático",
      "procedencia SQL",
      "admin, member y viewer",
      "RLS",
      "contexto del tenant controlado por el backend",
      "sin selector de tenant",
      "Disponible ahora",
      "Próximas capacidades",
      "Recorrido completo",
    ])
      expect(html).toContain(text);
  });

  it("keeps auth options evenly spaced under the submit action on desktop and narrow screens", () => {
    const styles = frontendCss();
    expect(styles).toMatch(
      /\.auth-links\s*\{[^}]*display:\s*grid[^}]*grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)[^}]*gap:/s,
    );
    expect(styles).toMatch(/\.auth-links a\s*\{[^}]*text-align:\s*center/s);
    expect(styles).toMatch(
      /@media\(max-width:720px\)\{[\s\S]*?\.auth-links\s*\{[^}]*grid-template-columns:\s*1fr/,
    );
    expect(styles).not.toMatch(
      /@media\(max-width:720px\)\{[\s\S]*?\.auth-links\s*\{[^}]*justify-content:\s*flex-start/,
    );
  });

  it("does not ship product-specific integrations or commercial content", () => {
    expect(page()).not.toMatch(
      /dvem|whatsapp|posthog|clarity|googletagmanager|google maps|mercado pago|pricing/i,
    );
  });
});
