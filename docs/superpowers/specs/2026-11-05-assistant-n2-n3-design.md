# Assistant N2/N3 — design

Date : 2026-11-05 · Branche : `claude/new-session-8c4szi` · Statut : design validé, spec à relire

## 1. Objectif

Faire évoluer l'outil existant (fichier HTML unique « DELFOS – SOC Investigation », 233 Ko, 1363 lignes, interface en français) en **« Assistant N2/N3 »** :

- renommer l'outil en « Assistant N2/N3 » ;
- ajouter un parcours N3 à côté du N2 QRadar déjà présent ;
- le livrer comme **Artifact privé** (IA et dossiers partagés actifs) **et** comme copie du HTML dans ce dépôt.

Utilisateur visé : analyste SOC N2/N3 travaillant sur IBM QRadar (et d'autres SIEM), dans un SOC multi-clients.

## 2. État actuel (vérifié dans le fichier source)

- Menu : Dashboard, Investigation, Dossiers, Clients, Alert Workflow, IOC Analysis, Threat Hunting, QRadar N2, MITRE ATT&CK, Reports, Settings.
- Bibliothèque de règles `R` (+ `NR`) : chaque règle porte une tactique et une technique MITRE (`m`), des requêtes Elastic/Splunk/KQL et des recommandations d'une ligne « N2 : … » / « N3 : … ».
- Assistant IA : `const AI={sample,db,user,…}`, initialisé par `claude.use("sample"|"db"|"user")`. Dossiers dans `cases`, clients dans `clients` (base partagée). Fonctions : `caseDoc`, `upd`, `addNote(texte, type)` (60 notes max, 4000 caractères), `investigate`, `ask`, `promptFor`.
- Onglet « QRadar N2 » : contenu statique + IIFE en fin de fichier (générateur AQL, checklist, quiz). Il n'est relié ni à l'IA ni aux dossiers.
- Sans `window.claude`, l'application fonctionne déjà en mode dégradé (`AI.ready`, `aiAvail()`).

## 3. Décisions validées avec l'utilisateur

| Sujet | Décision |
|---|---|
| Approche | Étendre l'application existante (pas de refonte, pas d'agent/skill séparé) |
| Modules N3 | Hunting par hypothèses · Triage DFIR · Playbooks de réponse + retex · Detection engineering |
| Structure | Un onglet **« Parcours N3 »** avec 4 sous-onglets, relié au dossier actif |
| Nom | « Assistant N2/N3 » |
| Livraison | Artifact privé + copie du HTML dans le dépôt, sur la branche désignée, **sans pull request** |

## 4. Architecture

- **Un seul fichier HTML.** Ajouts : bouton `data-v="n3"` « Parcours N3 » dans `nav` (après « QRadar N2 »), `<section class="view" id="v-n3">`, bloc CSS `/* v5 : parcours N3 */` (variables et classes existantes : `--ac`, `--bd`, `.card`, `.grid`, `.btn`, `.tag`, `.qr-callout`…), bloc JS `/* v5 */` en IIFE inséré avant l'appel final `dash();views();`.
- **Sous-onglets** : `Hunting`, `DFIR`, `Réponse & retex`, `Detection engineering`. Boutons avec `role="tab"` / `aria-selected`, navigation au clavier. Contenu rendu depuis des tableaux de données JS (`N3.hunt`, `N3.dfir`, `N3.ir`, `N3.det`), pas du HTML en dur.
- **Fichier dans le dépôt** : `assistant-n2-n3/assistant-n2-n3.html`.

### 4.1 Lien avec le dossier

- Bandeau en tête de l'onglet : « Dossier actif : <titre> » (via `caseDoc()`) ou « Aucun dossier ouvert : mode référence ».
- Bouton **« Enregistrer dans le dossier »** dans chaque sous-onglet : appelle `addNote(texte, type)` avec `type` ∈ `n3-hunt`, `n3-dfir`, `n3-ir`, `n3-det`. Désactivé, avec un message explicite, si `AI.db` est absent, si aucun dossier n'est ouvert ou si `AI.canWrite` est faux.
- Le texte enregistré est limité à 4000 caractères ; au-delà, il est tronqué avec une mention visible.

### 4.2 Lien avec l'IA

- Bouton **« Demander à l'assistant »** par sous-onglet, actif seulement si `AI.sample` existe et qu'un dossier est ouvert.
- Rien n'est envoyé avant le clic. L'envoi reprend le contexte déjà utilisé par l'assistant actuel (dossier + client sélectionné) plus une consigne propre au module, via le chemin d'appel existant (`promptFor` / `AI.sample`). Aucun autre échange de données.
- Consigne commune : distinguer fait observé, hypothèse et élément non vérifié ; ne rien affirmer sans preuve dans le dossier ; ne proposer aucune action comme exécutée ; toute action disruptive (blocage, désactivation de compte, isolement) est une recommandation soumise aux validations du SOC.
- La réponse s'affiche dans le sous-onglet. L'enregistrement dans le dossier reste un geste explicite.

## 5. Renommage

À remplacer par « Assistant N2/N3 » (et « L2/L3 » par « N2/N3 ») partout où c'est **visible** :

- `<title>` ; logo (`DELFOS` → « Assistant N2/N3 », sous-titre adapté) ;
- texte d'introduction de l'onglet QRadar et section « À propos » des réglages ;
- en-têtes des rapports Markdown (`# DELFOS – …`) et PDF (`#DELFOS - Rapport de Threat Hunting`), pied « Rapport généré par DELFOS » ;
- noms de fichiers générés (`delfos-hunting-….pdf`, `ticket-delfos-….pdf`) ;
- messages d'interface (« ouvrez DELFOS dans Claude… », « équipe SOC qui a accès à DELFOS », « Comme le réglage DELFOS ») ;
- prompt système (« Tu es l'assistant d'un analyste SOC L2/L3 » → N2/N3, « détections DELFOS » → « détections de l'outil »).

**Inchangés :** les clés `localStorage` `delfos-siem` et `delfos-client` (pour conserver les réglages existants) et, au plus, les commentaires de code internes.

## 6. Modules

### 6.1 Hunting par hypothèses

- Entrée : choix d'une tactique puis d'une technique, issues des règles de `R`/`NR` (champ `m`).
- Sortie par technique : modèle d'hypothèse (« Si <technique> a eu lieu, on doit observer … »), sources de données nécessaires, requêtes déjà portées par la règle (Elastic/Splunk/KQL) et un **modèle AQL** quand les champs QRadar standard le permettent ; sinon la carte indique « pas de modèle AQL : propriété personnalisée requise ». Tout AQL est marqué « à valider dans votre environnement ».
- Résultat noté par l'analyste : `Trouvé` · `Non trouvé` · `Non concluant` · `Données manquantes`, avec commentaire. Export vers une note de dossier ou copie.

### 6.2 Triage DFIR

- Checklists par type d'hôte (Windows, Linux, cloud, réseau), ordonnées par volatilité (mémoire → processus et connexions → journaux → disque), cochables.
- Modèle de chaîne de preuve : collecteur, date/heure UTC, source, hash, lieu de stockage, transferts.
- Avertissement permanent : préserver avant d'isoler ; acquisition et isolation exigent une autorisation.
- **Assistant de timeline** : l'analyste colle des lignes `horodatage | source | événement`. Horodatages acceptés : ISO 8601, `AAAA-MM-JJ HH:MM:SS[.mmm]` avec `Z` ou décalage `±hh:mm` (sans indication = UTC, signalé). Tri en UTC, tableau Markdown copiable ; lignes illisibles conservées en fin de liste, signalées. Traitement 100 % local.

### 6.3 Réponse & retex

- Playbooks pour cinq scénarios : compromission de compte, ransomware, phishing/malware, exfiltration, exploitation d'application web.
- Phases : confinement → éradication → restauration → communication. Chaque étape est cochable ; celles qui exigent une validation sont marquées « validation requise ». L'état des cases n'est conservé qu'en mémoire ; l'enregistrement dans le dossier écrit la liste avec son état.
- Retex : modèle structuré (chronologie, cause racine, ce qui a fonctionné, détection manquée, actions correctives avec responsable et échéance).

### 6.4 Detection engineering

- **Couverture MITRE** calculée à partir de `R`/`NR` ; trous = tactiques sans règle + techniques d'une liste de référence embarquée (≤ 3 par tactique) absentes de la bibliothèque.
- **Fiche de réglage d'un faux positif** : règle, symptôme, cause, exception proposée, risque de masquage, test avant/après, retour arrière, approbateur. Export vers note ou copie.
- **Idées de règles** à partir des trous : description de la logique de détection en langage clair + squelette AQL à valider.

## 7. Sécurité et gestion des erreurs

- Toute valeur saisie par l'utilisateur ou renvoyée par l'IA est échappée (`esc()`) ou rendue en texte brut avant insertion dans le DOM ; pour la réponse IA on réutilise `mdLite`/`renderAn`, qui existent déjà.
- IP validées par regex avant tout gabarit de requête (comme `#qr-ip`).
- Aucun nouvel appel réseau ; aucune action exécutée sur un SIEM ou un poste.
- Échecs de la base (`dbMsg`) ou de l'IA (`aiMsg`) : message visible dans le sous-onglet, jamais silencieux, sans perte du texte saisi.
- Mode dégradé (pas de `window.claude`) : modules en mode référence, boutons IA/dossier désactivés avec explication.

## 8. Vérifications

Chromium (Playwright), avec et sans simulation de `claude.use` :

1. Aucune erreur console au chargement et en naviguant dans l'application.
2. Les quatre sous-onglets s'affichent ; navigation clavier opérationnelle.
3. Hunting : génération de requêtes et de la carte d'hypothèse pour au moins une technique de chaque tactique couverte.
4. Timeline : tri correct sur un jeu de lignes mélangeant formats et fuseaux, y compris une ligne illisible.
5. Enregistrement : une note `n3-*` apparaît dans un dossier simulé ; refus géré quand `canWrite` est faux.
6. Renommage : aucun « DELFOS » ni « L2/L3 » dans le texte visible ni dans les fichiers générés ; clés `localStorage` inchangées.
7. Affichage : 390 px sans défilement horizontal ; thèmes clair et sombre lisibles.
8. Le fichier publié et la copie du dépôt sont identiques.

## 9. Livraison

1. Copie de base du fichier source dans `assistant-n2-n3/assistant-n2-n3.html`, puis modifications.
2. Publication de l'Artifact privé (capacités déclarées selon le skill `artifact-capabilities`), avec lien rendu à l'utilisateur.
3. Commit(s) sur `claude/new-session-8c4szi` et push ; **pas de pull request**.

## 10. Risques et points à vérifier à l'implémentation

- Le fichier appelle `claude.use("sample"|"db"|"user")`. Si le runtime Artifact actuel expose une autre API (`window.claude.*`), adapter le pont d'initialisation sans changer le comportement visible.
- Vérifier que le rendu des notes de dossier (`fillCase`) gère un `type` inconnu (`n3-*`) ; sinon l'ajouter au rendu.
- Le menu passe à 12 boutons : vérifier l'affichage mobile (barre horizontale défilable).
- Les modèles AQL dépendent de la version et de la configuration QRadar : toujours présentés comme « à valider ».

## 11. Hors périmètre

- Connexion à une console QRadar ou à toute API de threat intelligence.
- Exécution d'actions de réponse (blocage, isolement, désactivation).
- Réécriture du moteur de détection, d'extraction ou de la bibliothèque de règles existants.
- Autres SIEM que ceux déjà gérés par le réglage SIEM actuel.
