import { screen, waitFor, within } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import { apiError, FakeBackend, status } from "../test/backend";
import { makeAudit, makeEntry, makeScan, makeUser } from "../test/fixtures";
import { renderApp } from "../test/render";

const admin = () => makeUser({ role: "admin", email: "admin@acme.example.com" });

describe("scope", () => {
  it("lists authorised entries with readable kinds and network classes", async () => {
    new FakeBackend()
      .signedIn(admin())
      .on("GET /api/v1/scope/entries", [
        makeEntry({ kind: "domain", value: "acme.example.com", include_subdomains: true }),
        makeEntry({
          kind: "cidr",
          value: "10.20.0.0/16",
          network_class: "internal",
          include_subdomains: false,
          description: null,
        }),
      ])
      .install();
    renderApp("/scope");

    const table = await screen.findByRole("table", { name: "Périmètre autorisé" });
    expect(within(table).getByText("acme.example.com")).toBeInTheDocument();
    expect(within(table).getByText("Domaine")).toBeInTheDocument();
    expect(within(table).getByText("Plage CIDR")).toBeInTheDocument();
    expect(within(table).getByText("Interne")).toBeInTheDocument();
    expect(
      screen.getByText("Aucune cible ne peut être analysée sans autorisation explicite."),
    ).toBeInTheDocument();
  });

  it("explains that nothing can be scanned until something is authorised", async () => {
    new FakeBackend().signedIn(admin()).install();
    renderApp("/scope");
    expect(await screen.findByText(/Aucune autorisation configurée\./)).toBeInTheDocument();
  });

  it("lets an administrator add an entry and refreshes the list", async () => {
    const entries = [] as ReturnType<typeof makeEntry>[];
    const backend = new FakeBackend()
      .signedIn(admin())
      .on("GET /api/v1/scope/entries", () => entries)
      .on("POST /api/v1/scope/entries", ({ body }) => {
        const b = body as { kind: "domain"; value: string };
        const entry = makeEntry({ kind: b.kind, value: b.value });
        entries.push(entry);
        return status(201, entry);
      })
      .install();
    const { user } = renderApp("/scope");

    await screen.findByRole("heading", { name: "Ajouter une autorisation" });
    await user.type(screen.getByLabelText("Valeur"), "new.acme.example.com");
    await user.click(screen.getByLabelText("Inclure les sous-domaines"));
    await user.type(screen.getByLabelText("Description (optionnel)"), "staging");
    await user.click(screen.getByRole("button", { name: "Ajouter" }));

    expect(await screen.findByText("new.acme.example.com")).toBeInTheDocument();
    expect(backend.called("POST", "/api/v1/scope/entries")[0]?.body).toEqual({
      kind: "domain",
      value: "new.acme.example.com",
      include_subdomains: true,
      description: "staging",
    });
  });

  it("only offers 'include subdomains' for domains", async () => {
    new FakeBackend().signedIn(admin()).install();
    const { user } = renderApp("/scope");
    await screen.findByRole("heading", { name: "Ajouter une autorisation" });
    expect(screen.getByLabelText("Inclure les sous-domaines")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Type"), "cidr");
    expect(screen.queryByLabelText("Inclure les sous-domaines")).not.toBeInTheDocument();
  });

  it("never sends include_subdomains for a CIDR, even if it was ticked for a domain first", async () => {
    const backend = new FakeBackend()
      .signedIn(admin())
      .on("POST /api/v1/scope/entries", status(201, makeEntry()))
      .install();
    const { user } = renderApp("/scope");
    await user.click(await screen.findByLabelText("Inclure les sous-domaines"));
    await user.selectOptions(screen.getByLabelText("Type"), "cidr");
    await user.type(screen.getByLabelText("Valeur"), "10.20.0.0/16");
    await user.click(screen.getByRole("button", { name: "Ajouter" }));
    await waitFor(() => expect(backend.called("POST", "/api/v1/scope/entries")).toHaveLength(1));
    expect(backend.called("POST", "/api/v1/scope/entries")[0]?.body).toEqual({
      kind: "cidr",
      value: "10.20.0.0/16",
      include_subdomains: false,
    });
  });

  it("shows the server's explanation when an entry is refused", async () => {
    new FakeBackend()
      .signedIn(admin())
      .on(
        "POST /api/v1/scope/entries",
        status(
          422,
          apiError("validation_failed", "CIDR is too broad: /8 is shorter than the allowed /16"),
        ),
      )
      .install();
    const { user } = renderApp("/scope");
    await user.selectOptions(await screen.findByLabelText("Type"), "cidr");
    await user.type(screen.getByLabelText("Valeur"), "10.0.0.0/8");
    await user.click(screen.getByRole("button", { name: "Ajouter" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("CIDR is too broad");
  });

  it("reports duplicates in plain language", async () => {
    new FakeBackend()
      .signedIn(admin())
      .on(
        "POST /api/v1/scope/entries",
        status(409, apiError("conflict", "this scope entry already exists")),
      )
      .install();
    const { user } = renderApp("/scope");
    await user.type(await screen.findByLabelText("Valeur"), "acme.example.com");
    await user.click(screen.getByRole("button", { name: "Ajouter" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Cette autorisation existe déjà.");
  });

  it("deletes an entry only after an explicit confirmation", async () => {
    let entries = [makeEntry({ id: "e1", value: "acme.example.com" })];
    const backend = new FakeBackend()
      .signedIn(admin())
      .on("GET /api/v1/scope/entries", () => entries)
      .on("DELETE /api/v1/scope/entries/e1", () => {
        entries = [];
        return status(204);
      })
      .install();
    const { user } = renderApp("/scope");

    await user.click(await screen.findByRole("button", { name: "Supprimer acme.example.com" }));
    expect(backend.called("DELETE", "/api/v1/scope/entries/e1")).toHaveLength(0); // not yet
    await user.click(
      screen.getByRole("button", { name: "Annuler la suppression de acme.example.com" }),
    );
    expect(backend.called("DELETE", "/api/v1/scope/entries/e1")).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Supprimer acme.example.com" }));
    await user.click(
      screen.getByRole("button", { name: "Confirmer la suppression de acme.example.com" }),
    );
    expect(await screen.findByText(/Aucune autorisation configurée\./)).toBeInTheDocument();
    expect(backend.called("DELETE", "/api/v1/scope/entries/e1")).toHaveLength(1);
  });

  it("is read-only for viewers", async () => {
    new FakeBackend()
      .signedIn(makeUser({ role: "viewer" }))
      .on("GET /api/v1/scope/entries", [makeEntry({ value: "acme.example.com" })])
      .install();
    renderApp("/scope");
    await screen.findByText("acme.example.com");
    expect(
      screen.queryByRole("heading", { name: "Ajouter une autorisation" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Supprimer/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Tester une cible" })).not.toBeInTheDocument();
  });

  it("dry-runs a target and shows the verdict and validated addresses", async () => {
    const backend = new FakeBackend()
      .signedIn(makeUser({ role: "analyst" }))
      .on("POST /api/v1/scope/check", ({ body }) =>
        (body as { target: string }).target === "app.acme.example.com"
          ? {
              allowed: true,
              reason: null,
              target: "app.acme.example.com",
              pinned_ips: ["93.184.216.34"],
              matched_rule_ids: ["r1"],
              details: {},
            }
          : {
              allowed: false,
              reason: "not_in_scope",
              target: "evil.example.net",
              pinned_ips: [],
              matched_rule_ids: [],
              details: {},
            },
      )
      .install();
    const { user } = renderApp("/scope");

    await user.type(await screen.findByLabelText("Cible à tester"), "app.acme.example.com");
    await user.click(screen.getByRole("button", { name: "Tester" }));
    const verdict = await screen.findByRole("status", { name: "Résultat du test" });
    expect(verdict).toHaveTextContent("Autorisée");
    expect(verdict).toHaveTextContent("93.184.216.34");

    await user.clear(screen.getByLabelText("Cible à tester"));
    await user.type(screen.getByLabelText("Cible à tester"), "evil.example.net");
    await user.click(screen.getByRole("button", { name: "Tester" }));
    expect(await screen.findByText("Refusée : hors du périmètre autorisé.")).toBeInTheDocument();
    expect(backend.called("POST", "/api/v1/scope/check")).toHaveLength(2);
  });

  it("has no accessibility violations", async () => {
    new FakeBackend().signedIn(admin()).on("GET /api/v1/scope/entries", [makeEntry()]).install();
    const { container } = renderApp("/scope");
    await screen.findByRole("table", { name: "Périmètre autorisé" });
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("users", () => {
  it("lists users and lets an administrator change a role", async () => {
    const other = makeUser({
      id: "u2",
      email: "analyst@acme.example.com",
      role: "analyst",
      last_login_at: null,
    });
    const backend = new FakeBackend()
      .signedIn(admin())
      .on("GET /api/v1/users", [makeUser({ id: "u1", email: "admin@acme.example.com" }), other])
      .on("PATCH /api/v1/users/u2", ({ body }) => ({ ...other, ...(body as object) }))
      .install();
    const { user } = renderApp("/users");

    const table = await screen.findByRole("table", { name: "Utilisateurs de l'organisation" });
    expect(within(table).getByText("analyst@acme.example.com")).toBeInTheDocument();
    expect(within(table).getByText("Jamais")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Rôle de analyst@acme.example.com"), "viewer");
    await screen.findByRole("status", { name: "Notification" });
    expect(backend.called("PATCH", "/api/v1/users/u2")[0]?.body).toEqual({ role: "viewer" });
  });

  it("creates a user and reports duplicates clearly", async () => {
    const backend = new FakeBackend()
      .signedIn(admin())
      .on("GET /api/v1/users", [makeUser({ id: "u1" })])
      .on(
        "POST /api/v1/users",
        status(409, apiError("conflict", "a user with this e-mail already exists")),
      )
      .install();
    const { user } = renderApp("/users");

    await user.type(await screen.findByLabelText("E-mail"), "new@acme.example.com");
    await user.type(screen.getByLabelText("Mot de passe"), "a long enough passphrase");
    await user.selectOptions(screen.getByLabelText("Rôle"), "analyst");
    await user.click(screen.getByRole("button", { name: "Créer l'utilisateur" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Un utilisateur avec cet e-mail existe déjà.",
    );
    expect(backend.called("POST", "/api/v1/users")[0]?.body).toEqual({
      email: "new@acme.example.com",
      password: "a long enough passphrase",
      role: "analyst",
    });
  });

  it("surfaces the last-administrator protection", async () => {
    const me = makeUser({ id: "u1", email: "admin@acme.example.com" });
    new FakeBackend()
      .signedIn(me)
      .on("GET /api/v1/users", [me])
      .on(
        "PATCH /api/v1/users/u1",
        status(
          409,
          apiError("conflict", "cannot demote or deactivate the last active administrator"),
        ),
      )
      .install();
    const { user } = renderApp("/users");
    await user.click(
      await screen.findByRole("button", { name: "Désactiver admin@acme.example.com" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("last active administrator");
  });
});

describe("audit log", () => {
  it("shows events with readable outcomes and filters by action", async () => {
    const backend = new FakeBackend()
      .signedIn(admin())
      .on("GET /api/v1/audit-logs", ({ url }) =>
        url.searchParams.get("action") === "scan.create"
          ? [makeAudit({ id: 3, action: "scan.create", outcome: "denied" })]
          : [
              makeAudit({ id: 2, action: "auth.login", outcome: "success" }),
              makeAudit({ id: 1, action: "scope.create", outcome: "failure" }),
            ],
      )
      .install();
    const { user } = renderApp("/audit");

    const table = await screen.findByRole("table", { name: "Événements d'audit" });
    expect(within(table).getByText("Succès")).toBeInTheDocument();
    expect(within(table).getByText("Échec")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Filtrer par action"), "scan.create");
    expect(await screen.findByText("Refusé")).toBeInTheDocument();
    expect(
      backend
        .called("GET", "/api/v1/audit-logs")
        .some((c) => c.query.includes("action=scan.create")),
    ).toBe(true);
  });

  it("paginates with previous / next", async () => {
    const page = (offset: number) =>
      Array.from({ length: 25 }, (_, i) =>
        makeAudit({ id: 100 - offset - i, action: `evt.${String(offset + i)}` }),
      );
    new FakeBackend()
      .signedIn(admin())
      .on("GET /api/v1/audit-logs", ({ url }) => page(Number(url.searchParams.get("offset") ?? 0)))
      .install();
    const { user } = renderApp("/audit");
    await screen.findByText("evt.0");
    expect(screen.getByRole("button", { name: "Précédent" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Suivant" }));
    expect(await screen.findByText("evt.25")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Précédent" })).toBeEnabled();
  });

  it("shows an empty state", async () => {
    new FakeBackend().signedIn(admin()).install();
    renderApp("/audit");
    expect(await screen.findByText("Aucun événement.")).toBeInTheDocument();
  });
});

describe("settings", () => {
  it("shows the profile, the version and the signature", async () => {
    new FakeBackend()
      .signedIn(makeUser({ email: "root@acme.example.com", role: "analyst" }))
      .install();
    renderApp("/settings");
    expect(await screen.findByRole("heading", { name: "Paramètres" })).toBeInTheDocument();
    expect(screen.getByText("Connecté en tant que root@acme.example.com")).toBeInTheDocument();
    expect(screen.getByText("Analyste")).toBeInTheDocument();
    expect(await screen.findByText("Version 0.1.0")).toBeInTheDocument();
  });

  it("checks the confirmation before calling the API", async () => {
    const backend = new FakeBackend().signedIn(admin()).install();
    const { user } = renderApp("/settings");
    await user.type(await screen.findByLabelText("Mot de passe actuel"), "current password 1");
    await user.type(screen.getByLabelText("Nouveau mot de passe"), "another long passphrase");
    await user.type(
      screen.getByLabelText("Confirmer le nouveau mot de passe"),
      "something different!!",
    );
    await user.click(screen.getByRole("button", { name: "Changer le mot de passe" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Les mots de passe ne correspondent pas.",
    );
    expect(backend.called("POST", "/api/v1/auth/change-password")).toHaveLength(0);
  });

  it("rejects a wrong current password", async () => {
    new FakeBackend()
      .signedIn(admin())
      .on(
        "POST /api/v1/auth/change-password",
        status(401, apiError("authentication_failed", "invalid credentials")),
      )
      .install();
    const { user } = renderApp("/settings");
    await user.type(await screen.findByLabelText("Mot de passe actuel"), "wrong password!!");
    await user.type(screen.getByLabelText("Nouveau mot de passe"), "another long passphrase");
    await user.type(
      screen.getByLabelText("Confirmer le nouveau mot de passe"),
      "another long passphrase",
    );
    await user.click(screen.getByRole("button", { name: "Changer le mot de passe" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Mot de passe actuel incorrect.");
  });

  it("signs out after a successful change because every session was revoked", async () => {
    const backend = new FakeBackend()
      .signedIn(admin())
      .on("POST /api/v1/auth/change-password", status(204))
      .install();
    const { user } = renderApp("/settings");
    await user.type(await screen.findByLabelText("Mot de passe actuel"), "current password 1");
    await user.type(screen.getByLabelText("Nouveau mot de passe"), "another long passphrase");
    await user.type(
      screen.getByLabelText("Confirmer le nouveau mot de passe"),
      "another long passphrase",
    );
    await user.click(screen.getByRole("button", { name: "Changer le mot de passe" }));

    expect(await screen.findByRole("heading", { name: "Connexion" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Mot de passe modifié. Veuillez vous reconnecter.",
    );
    expect(backend.called("POST", "/api/v1/auth/change-password")[0]?.body).toEqual({
      old_password: "current password 1",
      new_password: "another long passphrase",
    });
  });
});

describe("dashboard", () => {
  it("summarises the platform for an administrator", async () => {
    new FakeBackend()
      .signedIn(admin())
      .on("GET /api/v1/scans", [
        makeScan({ id: "s1", status: "succeeded", target: "a.acme.example.com" }),
        makeScan({ id: "s2", status: "running", target: "b.acme.example.com" }),
        makeScan({ id: "s3", status: "failed", target: "c.acme.example.com" }),
      ])
      .on("GET /api/v1/scope/entries", [makeEntry(), makeEntry({ value: "other.example.com" })])
      .on("GET /api/v1/audit-logs", [makeAudit({ action: "scan.create" })])
      .install();
    renderApp("/");

    const api = await screen.findByRole("region", { name: "État de l'API" });
    expect(await within(api).findByText("Opérationnelle")).toBeInTheDocument();
    const scans = screen.getByRole("region", { name: "Scans" });
    expect(await within(scans).findByText("3")).toBeInTheDocument();
    expect(within(scans).getByText("En cours : 1")).toBeInTheDocument();
    const scope = screen.getByRole("region", { name: "Autorisations de périmètre" });
    expect(await within(scope).findByText("2")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "b.acme.example.com" })).toBeInTheDocument();
    const activity = await screen.findByRole("region", { name: "Activité récente" });
    expect(await within(activity).findByText("scan.create")).toBeInTheDocument();
  });

  it("reports a degraded API", async () => {
    new FakeBackend()
      .signedIn(admin())
      .on(
        "GET /health/ready",
        status(503, { status: "degraded", checks: { database: "ok", redis: "fail" } }),
      )
      .install();
    renderApp("/");
    const api = await screen.findByRole("region", { name: "État de l'API" });
    expect(await within(api).findByText("Dégradée")).toBeInTheDocument();
  });

  it("hides the activity panel from non-administrators", async () => {
    new FakeBackend().signedIn(makeUser({ role: "viewer" })).install();
    renderApp("/");
    await screen.findByRole("heading", { name: "Tableau de bord" });
    expect(screen.queryByRole("region", { name: "Activité récente" })).not.toBeInTheDocument();
  });
});
