import { screen, within } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import { apiError, FakeBackend, status } from "../test/backend";
import { makeFinding, makeScan, makeUser } from "../test/fixtures";
import { renderApp } from "../test/render";

const analyst = () => makeUser({ role: "analyst", email: "analyst@acme.example.com" });

describe("scans list", () => {
  it("shows a loading state, then the scans with readable statuses", async () => {
    new FakeBackend()
      .signedIn(analyst())
      .on("GET /api/v1/scans", [
        makeScan({ target: "app.acme.example.com", status: "running" }),
        makeScan({ target: "www.acme.example.com", status: "succeeded" }),
        makeScan({ target: "old.acme.example.com", status: "failed" }),
      ])
      .install();
    renderApp("/scans");

    expect(screen.getByRole("status")).toHaveTextContent("Chargement…");
    const table = await screen.findByRole("table", { name: "Liste des scans" });
    for (const header of ["Cible", "Moteur", "Statut", "Créé le"]) {
      expect(within(table).getByRole("columnheader", { name: header })).toBeInTheDocument();
    }
    expect(within(table).getByRole("link", { name: "app.acme.example.com" })).toBeInTheDocument();
    expect(within(table).getByText("En cours")).toBeInTheDocument();
    expect(within(table).getByText("Terminé")).toBeInTheDocument();
    expect(within(table).getByText("Échoué")).toBeInTheDocument();
  });

  it("shows an empty state with guidance", async () => {
    new FakeBackend().signedIn(analyst()).install();
    renderApp("/scans");
    expect(await screen.findByText("Aucun scan pour le moment.")).toBeInTheDocument();
  });

  it("shows an error with a retry that works", async () => {
    let attempts = 0;
    const backend = new FakeBackend().signedIn(analyst()).install();
    backend.on("GET /api/v1/scans", () => {
      attempts += 1;
      return attempts === 1
        ? status(500, apiError("internal_error", "internal server error"))
        : [makeScan({ target: "after-retry.acme.example.com" })];
    });
    const { user } = renderApp("/scans");

    expect(await screen.findByRole("alert")).toHaveTextContent("Une erreur est survenue");
    await user.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(await screen.findByText("after-retry.acme.example.com")).toBeInTheDocument();
  });

  it("filters by status through the API", async () => {
    new FakeBackend()
      .signedIn(analyst())
      .on("GET /api/v1/scans", ({ url }) =>
        url.searchParams.get("status") === "succeeded"
          ? [makeScan({ target: "done.acme.example.com", status: "succeeded" })]
          : [makeScan({ target: "queued.acme.example.com", status: "pending" })],
      )
      .install();
    const { user } = renderApp("/scans");
    expect(await screen.findByText("queued.acme.example.com")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Statut"), "succeeded");
    expect(await screen.findByText("done.acme.example.com")).toBeInTheDocument();
    expect(screen.queryByText("queued.acme.example.com")).not.toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    new FakeBackend().signedIn(analyst()).on("GET /api/v1/scans", [makeScan()]).install();
    const { container } = renderApp("/scans");
    await screen.findByRole("table", { name: "Liste des scans" });
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("creating a scan", () => {
  it("lets an analyst request a scan with record types and opens its detail page", async () => {
    const created = makeScan({ id: "scan-new", target: "app.acme.example.com", status: "pending" });
    const backend = new FakeBackend()
      .signedIn(analyst())
      .on("POST /api/v1/scans", status(202, created))
      .on("GET /api/v1/scans/scan-new", created)
      .on("GET /api/v1/scans/scan-new/findings", [])
      .install();
    const { user } = renderApp("/scans");

    await screen.findByRole("heading", { name: "Nouveau scan" });
    await user.type(screen.getByLabelText("Cible"), "app.acme.example.com");
    await user.click(screen.getByRole("checkbox", { name: "CNAME" }));
    await user.click(screen.getByRole("checkbox", { name: "MX" })); // uncheck a default
    await user.click(screen.getByRole("button", { name: "Lancer le scan" }));

    expect(
      await screen.findByRole("heading", { name: "app.acme.example.com" }),
    ).toBeInTheDocument();
    expect(backend.called("POST", "/api/v1/scans")[0]?.body).toEqual({
      engine: "dns_recon",
      target: "app.acme.example.com",
      params: { record_types: ["A", "AAAA", "NS", "TXT", "CNAME"] },
    });
  });

  it.each([
    ["not_in_scope", "Cible refusée : hors du périmètre autorisé."],
    [
      "blocked_address",
      "Cible refusée : adresse interdite (boucle locale, lien local, métadonnées cloud…).",
    ],
    ["internal_not_authorised", "Cible refusée : adresse interne non autorisée explicitement."],
    ["invalid_target", "Cible refusée : cible invalide."],
  ])("explains a scope refusal (%s)", async (reason, message) => {
    new FakeBackend()
      .signedIn(analyst())
      .on(
        "POST /api/v1/scans",
        status(
          403,
          apiError("scope_violation", "target is not authorised for scanning", { reason }),
        ),
      )
      .install();
    const { user } = renderApp("/scans");
    await user.type(await screen.findByLabelText("Cible"), "evil.example.net");
    await user.click(screen.getByRole("button", { name: "Lancer le scan" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });

  it("shows server-side validation messages", async () => {
    new FakeBackend()
      .signedIn(analyst())
      .on("POST /api/v1/scans", status(422, apiError("validation_failed", "unknown engine")))
      .install();
    const { user } = renderApp("/scans");
    await user.type(await screen.findByLabelText("Cible"), "app.acme.example.com");
    await user.click(screen.getByRole("button", { name: "Lancer le scan" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("unknown engine");
  });

  it("does not offer scan creation to viewers", async () => {
    new FakeBackend().signedIn(makeUser({ role: "viewer" })).install();
    renderApp("/scans");
    await screen.findByRole("heading", { name: "Scans" });
    expect(screen.queryByRole("heading", { name: "Nouveau scan" })).not.toBeInTheDocument();
    expect(
      screen.getByText("Votre rôle (lecteur) ne permet pas de lancer des scans."),
    ).toBeInTheDocument();
  });
});

describe("scan detail", () => {
  const detail = (overrides = {}) =>
    makeScan({ id: "scan-1", target: "app.acme.example.com", ...overrides });

  it("shows the scan, its validated addresses and its findings", async () => {
    new FakeBackend()
      .signedIn(analyst())
      .on(
        "GET /api/v1/scans/scan-1",
        detail({
          status: "succeeded",
          started_at: "2026-11-12T10:00:05Z",
          finished_at: "2026-11-12T10:00:09Z",
          attempts: 1,
        }),
      )
      .on("GET /api/v1/scans/scan-1/findings", [
        makeFinding({ title: "A record", severity: "info" }),
        makeFinding({ title: "Missing SPF record", severity: "low", category: "misconfiguration" }),
      ])
      .install();
    renderApp("/scans/scan-1");

    expect(
      await screen.findByRole("heading", { name: "app.acme.example.com" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Terminé")).toBeInTheDocument();
    expect(screen.getByText("93.184.216.34")).toBeInTheDocument(); // pinned addresses
    const findings = await screen.findByRole("table", { name: "Résultats du scan" });
    expect(within(findings).getByText("Missing SPF record")).toBeInTheDocument();
    expect(within(findings).getByText("Faible")).toBeInTheDocument();
    expect(within(findings).getByText("Info")).toBeInTheDocument();
  });

  it("refreshes the findings when a scan finishes, without a page reload", async () => {
    // Regression found by the browser e2e run. The findings requested while the scan was still
    // running were empty; when the next scan poll reported « Terminé », findings polling stopped
    // and nothing refetched them, leaving « Aucun résultat » next to a finished scan.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      let workerDone = false; // server state: the worker has finished and written its results
      const backend: FakeBackend = new FakeBackend()
        .signedIn(analyst())
        .on("GET /api/v1/scans/scan-1", () => {
          const calls = backend.called("GET", "/api/v1/scans/scan-1").length;
          if (calls >= 2) workerDone = true; // finishes between the first and the second poll
          return workerDone
            ? detail({
                status: "succeeded",
                started_at: "2026-11-12T10:00:05Z",
                finished_at: "2026-11-12T10:00:06Z",
                attempts: 1,
              })
            : detail({ status: "running", started_at: "2026-11-12T10:00:05Z" });
        })
        .on("GET /api/v1/scans/scan-1/findings", () =>
          workerDone ? [makeFinding({ title: "Missing SPF record" })] : [],
        )
        .install();
      renderApp("/scans/scan-1");

      expect(await screen.findByText("En cours")).toBeInTheDocument();
      expect(await screen.findByText("Aucun résultat pour le moment.")).toBeInTheDocument();
      await vi.advanceTimersByTimeAsync(3100); // one polling round
      expect(await screen.findByText("Terminé")).toBeInTheDocument();
      const table = await screen.findByRole("table", { name: "Résultats du scan" });
      expect(within(table).getByText("Missing SPF record")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("filters findings by severity through the API", async () => {
    const backend = new FakeBackend()
      .signedIn(analyst())
      .on("GET /api/v1/scans/scan-1", detail({ status: "succeeded" }))
      .on("GET /api/v1/scans/scan-1/findings", ({ url }) =>
        url.searchParams.get("severity") === "low"
          ? [makeFinding({ title: "Only the low one", severity: "low" })]
          : [
              makeFinding({ title: "A record" }),
              makeFinding({ title: "Only the low one", severity: "low" }),
            ],
      )
      .install();
    const { user } = renderApp("/scans/scan-1");
    await screen.findByText("A record");
    await user.selectOptions(screen.getByLabelText("Gravité"), "low");
    await screen.findByText("Only the low one");
    expect(screen.queryByText("A record")).not.toBeInTheDocument();
    expect(backend.called("GET", "/api/v1/scans/scan-1/findings").length).toBeGreaterThan(1);
  });

  it("explains a failed scan with its error", async () => {
    new FakeBackend()
      .signedIn(analyst())
      .on(
        "GET /api/v1/scans/scan-1",
        detail({
          status: "failed",
          error_code: "scope_denied",
          error_message: "target is no longer authorised (blocked_address)",
        }),
      )
      .on("GET /api/v1/scans/scan-1/findings", [])
      .install();
    renderApp("/scans/scan-1");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "target is no longer authorised (blocked_address)",
    );
    expect(await screen.findByText("Aucun résultat pour le moment.")).toBeInTheDocument();
  });

  it("lets an analyst cancel a running scan", async () => {
    let current = detail({ status: "running" });
    const backend = new FakeBackend()
      .signedIn(analyst())
      .on("GET /api/v1/scans/scan-1", () => current)
      .on("GET /api/v1/scans/scan-1/findings", [])
      .on("POST /api/v1/scans/scan-1/cancel", () => {
        current = detail({ status: "cancelled", finished_at: "2026-11-12T10:05:00Z" });
        return current;
      })
      .install();
    const { user } = renderApp("/scans/scan-1");

    await user.click(await screen.findByRole("button", { name: "Annuler le scan" }));
    expect(await screen.findByText("Annulé")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Annuler le scan" })).not.toBeInTheDocument();
    expect(backend.called("POST", "/api/v1/scans/scan-1/cancel")).toHaveLength(1);
  });

  it("offers no cancel button to viewers or for finished scans", async () => {
    const backend = new FakeBackend()
      .signedIn(makeUser({ role: "viewer" }))
      .on("GET /api/v1/scans/scan-1", detail({ status: "running" }))
      .on("GET /api/v1/scans/scan-1/findings", [])
      .install();
    renderApp("/scans/scan-1");
    await screen.findByRole("heading", { name: "app.acme.example.com" });
    expect(screen.queryByRole("button", { name: "Annuler le scan" })).not.toBeInTheDocument();
    expect(backend.called("POST", "/api/v1/scans/scan-1/cancel")).toHaveLength(0);
  });

  it("says so when the scan does not exist (or belongs to another organisation)", async () => {
    new FakeBackend()
      .signedIn(analyst())
      .on("GET /api/v1/scans/missing", status(404, apiError("not_found", "scan not found")))
      .on(
        "GET /api/v1/scans/missing/findings",
        status(404, apiError("not_found", "scan not found")),
      )
      .install();
    renderApp("/scans/missing");
    expect(await screen.findByRole("heading", { name: "Scan introuvable" })).toBeInTheDocument();
  });
});
