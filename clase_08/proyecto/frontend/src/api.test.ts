import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  apiErrorMessage,
  createMember,
  appendExperimentResult,
  getExperiments,
  getDocuments,
  getDocument,
  getSession,
  updateMember,
  updateExperiment,
} from "./api";

beforeEach(() => {
  document.cookie = "csrf_token=token; path=/";
});
afterEach(() => {
  vi.restoreAllMocks();
});
describe("cookie API client", () => {
  it("sends cookies and CSRF for mutations", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("{}", { status: 201 }));
    await createMember("member@example.test", "viewer");
    expect(fetcher).toHaveBeenCalledWith(
      "/api/members",
      expect.objectContaining({
        credentials: "include",
        headers: expect.objectContaining({ "x-csrf-token": "token" }),
      }),
    );
  });
  it("updates a membership with PATCH, JSON payload, and CSRF", async () => {
    const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          membership_id: "membership-1",
          user_id: "member-1",
          role: "viewer",
          active: false,
        }),
        { status: 200 },
      ),
    );

    await expect(
      updateMember("membership-1", { role: "viewer", active: false }),
    ).resolves.toEqual({
      membership_id: "membership-1",
      user_id: "member-1",
      role: "viewer",
      active: false,
    });
    expect(fetcher).toHaveBeenCalledWith(
      "/api/members/membership-1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ role: "viewer", active: false }),
        credentials: "include",
        headers: expect.objectContaining({
          "content-type": "application/json",
          "x-csrf-token": "token",
        }),
      }),
    );
    expect(
      fetcher.mock.calls.some(([, init]) => init?.method === "DELETE"),
    ).toBe(false);
  });

  it("surfaces membership update errors in Spanish", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: "last admin cannot be deactivated" }),
        {
          status: 409,
        },
      ),
    );

    await expect(
      updateMember("membership-1", { active: false }),
    ).rejects.toThrow("No se pudo completar la solicitud por un conflicto.");
  });

  it("does not attach CSRF to session reads", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
    await getSession();
    expect(fetcher.mock.calls[0][1]?.headers).not.toHaveProperty(
      "x-csrf-token",
    );
  });

  it("sends terminal experiment closure in the result POST", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 201 }));

    await appendExperimentResult("experiment-1", {
      status: "completed",
      terminal_status: "completed",
      transition_reason: "verified",
      metrics: [],
    });

    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher).toHaveBeenCalledWith(
      "/api/experiments/experiment-1/results",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          status: "completed",
          terminal_status: "completed",
          transition_reason: "verified",
          metrics: [],
        }),
      }),
    );
  });

  it("omits empty experiment filters while preserving pagination and sorting", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    await getExperiments({
      page: 2,
      per_page: 25,
      search: "",
      status: "",
      archived: false,
      sort: "created_at:desc",
    });

    const url = new URL(String(fetcher.mock.calls[0][0]), "http://localhost");
    expect(url.searchParams.has("status")).toBe(false);
    expect(url.searchParams.has("search")).toBe(false);
    expect(url.searchParams.get("page")).toBe("2");
    expect(url.searchParams.get("per_page")).toBe("25");
    expect(url.searchParams.get("sort")).toBe("created_at:desc");
  });

  it("omits empty document filters while preserving pagination and sorting", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    await getDocuments({
      page: 2,
      per_page: 20,
      search: " ",
      status: "",
      sort: "name:asc",
    });

    const url = new URL(String(fetcher.mock.calls[0][0]), "http://localhost");
    expect(url.searchParams.has("status")).toBe(false);
    expect(url.searchParams.has("search")).toBe(false);
    expect(url.searchParams.get("page")).toBe("2");
    expect(url.searchParams.get("per_page")).toBe("20");
    expect(url.searchParams.get("sort")).toBe("name:asc");
  });

  it("encodes the document identifier for detail requests", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    await getDocument("document/id");

    expect(fetcher).toHaveBeenCalledWith(
      "/api/documents/document%2Fid",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("serializes nonempty document filters", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    await getDocuments({
      page: 1,
      per_page: 10,
      search: "guía",
      status: "ready",
      sort: "status:desc",
    });

    const url = new URL(String(fetcher.mock.calls[0][0]), "http://localhost");
    expect(url.searchParams.get("search")).toBe("guía");
    expect(url.searchParams.get("status")).toBe("ready");
    expect(url.searchParams.get("sort")).toBe("status:desc");
  });

  it("serializes nonempty experiment filters", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    await getExperiments({
      page: 1,
      per_page: 10,
      search: "baseline run",
      status: "running",
      archived: true,
      sort: "name:asc",
    });

    const url = new URL(String(fetcher.mock.calls[0][0]), "http://localhost");
    expect(url.searchParams.get("search")).toBe("baseline run");
    expect(url.searchParams.get("status")).toBe("running");
    expect(url.searchParams.get("archived")).toBe("true");
    expect(url.searchParams.get("page")).toBe("1");
    expect(url.searchParams.get("per_page")).toBe("10");
    expect(url.searchParams.get("sort")).toBe("name:asc");
  });

  it("updates experiment name, archive, and restore using PATCH only", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({}), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({}), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({}), { status: 200 }));

    await updateExperiment("experiment-1", { name: "Renombrado" });
    await updateExperiment("experiment-1", { archived: true });
    await updateExperiment("experiment-1", { archived: false });

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "/api/experiments/experiment-1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ name: "Renombrado" }),
      }),
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "/api/experiments/experiment-1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ archived: true }),
      }),
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      3,
      "/api/experiments/experiment-1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ archived: false }),
      }),
    );
    expect(
      fetcher.mock.calls.some(([, init]) => init?.method === "DELETE"),
    ).toBe(false);
  });

  it.each([
    [400, "La solicitud no es válida."],
    [401, "Se requiere autenticación."],
    [403, "No tenés permiso para realizar esta acción."],
    [404, "No se encontró el recurso solicitado."],
    [409, "No se pudo completar la solicitud por un conflicto."],
    [422, "Los datos enviados no son válidos."],
    [
      429,
      "Se realizaron demasiadas solicitudes. Intentá nuevamente más tarde.",
    ],
    [500, "Ocurrió un error interno. Intentá nuevamente más tarde."],
    [503, "Ocurrió un error interno. Intentá nuevamente más tarde."],
    [418, "No se pudo completar la solicitud."],
  ])("uses a Spanish fallback for HTTP %i", async (status, message) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status, statusText: "Unauthorized" }),
    );
    await expect(getSession()).rejects.toThrow(message);
  });

  it("never exposes statusText for non-JSON failures", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("<html>failure</html>", {
        status: 500,
        statusText: "Internal Server Error",
      }),
    );
    await expect(getSession()).rejects.toThrow(
      "Ocurrió un error interno. Intentá nuevamente más tarde.",
    );
  });

  it("normalizes legacy and structured validation errors without English leakage", () => {
    expect(apiErrorMessage("invalid credentials")).toBe(
      "El correo electrónico o la contraseña no son válidos.",
    );
    expect(apiErrorMessage("Se requiere autenticación.")).toBe(
      "Se requiere autenticación.",
    );
    expect(
      apiErrorMessage([
        {
          loc: ["body", "email"],
          type: "value_error",
          msg: "not a valid email",
        },
      ]),
    ).toBe("Ingresá un correo electrónico válido.");
    expect(
      apiErrorMessage([
        {
          loc: ["body", "password"],
          type: "string_too_short",
          msg: "String should have at least 8 characters",
        },
      ]),
    ).toBe("La contraseña debe tener al menos 8 caracteres.");
    expect(
      apiErrorMessage([
        { loc: ["body", "email"], type: "missing", msg: "Field required" },
      ]),
    ).toBe("Este campo es obligatorio.");
    expect(
      apiErrorMessage([
        {
          loc: ["body", "unknown"],
          type: "unexpected",
          msg: "English server exception",
        },
      ]),
    ).toBe("Los datos enviados no son válidos.");
  });

  it("uses the Spanish network failure", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      new TypeError("network unavailable"),
    );
    await expect(getSession()).rejects.toThrow("La API no está disponible.");
  });
});
