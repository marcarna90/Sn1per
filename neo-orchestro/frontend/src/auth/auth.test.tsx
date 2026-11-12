import { screen, within } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import { apiError, FakeBackend, status } from "../test/backend";
import { makeUser } from "../test/fixtures";
import { renderApp } from "../test/render";

const SIGNATURE = "Designed & Developed by Ronald TSR";

describe("session restore", () => {
  it("shows the login page when there is no valid session", async () => {
    new FakeBackend().signedOut().install();
    renderApp("/");
    expect(await screen.findByRole("heading", { name: "Connexion" })).toBeInTheDocument();
    expect(screen.getByText(SIGNATURE)).toBeInTheDocument();
  });

  it("restores the session from the refresh cookie", async () => {
    const backend = new FakeBackend()
      .signedIn(makeUser({ email: "root@acme.example.com" }))
      .install();
    renderApp("/");
    expect(await screen.findByRole("heading", { name: "Tableau de bord" })).toBeInTheDocument();
    expect(screen.getByText("root@acme.example.com")).toBeInTheDocument();
    expect(backend.called("POST", "/api/v1/auth/refresh")).toHaveLength(1);
    expect(backend.called("POST", "/api/v1/auth/refresh")[0]?.headers.get("X-Neo-CSRF")).toBe("1");
  });

  it("shows a loading state while the session is being checked", () => {
    new FakeBackend().signedOut().install();
    renderApp("/");
    expect(screen.getByRole("status")).toHaveTextContent("Chargement…");
  });
});

describe("login", () => {
  it("signs in with e-mail and password and lands on the dashboard", async () => {
    const backend = new FakeBackend().signedOut().install();
    const { user } = renderApp("/");
    await screen.findByRole("heading", { name: "Connexion" });

    backend
      .on("POST /api/v1/auth/login", {
        access_token: "tok-1",
        token_type: "bearer",
        expires_in: 900,
      })
      .signedIn(makeUser());
    await user.type(screen.getByLabelText("Adresse e-mail"), "admin@acme.example.com");
    await user.type(screen.getByLabelText("Mot de passe"), "correct horse battery");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));

    expect(await screen.findByRole("heading", { name: "Tableau de bord" })).toBeInTheDocument();
    expect(backend.called("POST", "/api/v1/auth/login")[0]?.body).toEqual({
      email: "admin@acme.example.com",
      password: "correct horse battery",
    });
  });

  it("shows one generic error for any rejected credentials and clears the password", async () => {
    const backend = new FakeBackend().signedOut().install();
    const { user } = renderApp("/");
    await screen.findByRole("heading", { name: "Connexion" });
    backend.on(
      "POST /api/v1/auth/login",
      status(401, apiError("authentication_failed", "invalid credentials")),
    );

    await user.type(screen.getByLabelText("Adresse e-mail"), "admin@acme.example.com");
    await user.type(screen.getByLabelText("Mot de passe"), "wrong password!!");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Identifiants invalides ou compte verrouillé.",
    );
    expect(screen.getByLabelText("Mot de passe")).toHaveValue("");
    expect(screen.getByRole("heading", { name: "Connexion" })).toBeInTheDocument();
  });

  it("reports an unreachable server distinctly from bad credentials", async () => {
    const backend = new FakeBackend().signedOut().install();
    const { user } = renderApp("/");
    await screen.findByRole("heading", { name: "Connexion" });
    backend.on("POST /api/v1/auth/login", () => {
      throw new TypeError("Failed to fetch");
    });
    await user.type(screen.getByLabelText("Adresse e-mail"), "a@acme.example.com");
    await user.type(screen.getByLabelText("Mot de passe"), "whatever-password");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de joindre le serveur.");
  });

  it("returns to the page that required authentication", async () => {
    const backend = new FakeBackend().signedOut().install();
    const { user } = renderApp("/scans");
    await screen.findByRole("heading", { name: "Connexion" });

    backend
      .on("POST /api/v1/auth/login", {
        access_token: "tok-1",
        token_type: "bearer",
        expires_in: 900,
      })
      .signedIn(makeUser());
    await user.type(screen.getByLabelText("Adresse e-mail"), "admin@acme.example.com");
    await user.type(screen.getByLabelText("Mot de passe"), "correct horse battery");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));

    expect(await screen.findByRole("heading", { name: "Scans" })).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    new FakeBackend().signedOut().install();
    const { container } = renderApp("/");
    await screen.findByRole("heading", { name: "Connexion" });
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("logout and session loss", () => {
  it("logs out, revokes the session server-side and clears cached data", async () => {
    const backend = new FakeBackend().signedIn(makeUser()).install();
    const { user } = renderApp("/");
    await screen.findByRole("heading", { name: "Tableau de bord" });

    await user.click(screen.getByRole("button", { name: "Se déconnecter" }));
    expect(await screen.findByRole("heading", { name: "Connexion" })).toBeInTheDocument();
    expect(backend.called("POST", "/api/v1/auth/logout")).toHaveLength(1);
    expect(backend.called("POST", "/api/v1/auth/logout")[0]?.headers.get("X-Neo-CSRF")).toBe("1");
  });

  it("explains an expired session when a request can no longer be refreshed", async () => {
    const backend = new FakeBackend().signedIn(makeUser()).install();
    const { user } = renderApp("/scans");
    await screen.findByRole("heading", { name: "Scans" });

    // From now on the server rejects the access token *and* the refresh cookie.
    const expired = status(401, apiError("authentication_failed", "expired"));
    backend.on("GET /api/v1/scans", expired).on("POST /api/v1/auth/refresh", expired);
    await user.selectOptions(screen.getByLabelText("Statut"), "pending"); // triggers a new request

    expect(await screen.findByRole("heading", { name: "Connexion" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Votre session a expiré. Veuillez vous reconnecter.",
    );
  });
});

describe("navigation and roles", () => {
  const labels = (nav: HTMLElement) =>
    within(nav)
      .getAllByRole("link")
      .map((link) => link.textContent);

  it("gives an administrator every section", async () => {
    new FakeBackend().signedIn(makeUser({ role: "admin" })).install();
    renderApp("/");
    const nav = await screen.findByRole("navigation", { name: "Navigation principale" });
    expect(labels(nav)).toEqual([
      "Tableau de bord",
      "Scans",
      "Périmètre",
      "Utilisateurs",
      "Journal d'audit",
      "Paramètres",
    ]);
  });

  it("hides administration from analysts and viewers", async () => {
    new FakeBackend().signedIn(makeUser({ role: "viewer" })).install();
    renderApp("/");
    const nav = await screen.findByRole("navigation", { name: "Navigation principale" });
    expect(labels(nav)).toEqual(["Tableau de bord", "Scans", "Périmètre", "Paramètres"]);
  });

  it("refuses direct access to an admin page with a clear message", async () => {
    const backend = new FakeBackend().signedIn(makeUser({ role: "analyst" })).install();
    renderApp("/users");
    expect(await screen.findByRole("heading", { name: "Accès refusé" })).toBeInTheDocument();
    expect(backend.called("GET", "/api/v1/users")).toHaveLength(0); // the request is never made
  });

  it("shows the signature in the application footer", async () => {
    new FakeBackend().signedIn(makeUser()).install();
    renderApp("/");
    await screen.findByRole("heading", { name: "Tableau de bord" });
    expect(within(screen.getByRole("contentinfo")).getByText(SIGNATURE)).toBeInTheDocument();
  });

  it("answers unknown pages with a not-found page", async () => {
    new FakeBackend().signedIn(makeUser()).install();
    renderApp("/nope/nothing");
    expect(await screen.findByRole("heading", { name: "Page introuvable" })).toBeInTheDocument();
  });

  it("offers a skip link and a labelled main landmark", async () => {
    new FakeBackend().signedIn(makeUser()).install();
    renderApp("/");
    await screen.findByRole("heading", { name: "Tableau de bord" });
    expect(screen.getByRole("link", { name: "Aller au contenu principal" })).toHaveAttribute(
      "href",
      "#main",
    );
    expect(screen.getByRole("main")).toHaveAttribute("id", "main");
  });
});
