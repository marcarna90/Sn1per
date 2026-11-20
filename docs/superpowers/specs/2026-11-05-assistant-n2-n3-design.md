# Assistant N2/N3 — design

Date : 2026-11-05 · Branche : `claude/new-session-8c4szi` · Statut : **implémenté** (voir `assistant-n2-n3/assistant-n2-n3.html`). Les écarts avec la première version de cette spec sont signalés « Mis à jour ».

## 1. Objectif

Faire évoluer l'outil existant (fichier HTML unique « DELFOS – SOC Investigation », 233 Ko, 1363 lignes, interface en français) en **« Assistant N2/N3 »** :

- renommer l'outil en « Assistant N2/N3 » ;
- ajouter un parcours N3 à côté du N2 QRadar déjà présent ;
- le livrer comme **fichier HTML autonome et téléchargeable** (Mis à jour : demande ultérieure de l'utilisateur, à la place d'un Artifact publié), avec une copie dans ce dépôt.

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
| Livraison | Mis à jour : **fichier HTML téléchargeable** + copie dans le dépôt, sur la branche désignée, **sans pull request**. Pas d'Artifact publié (l'utilisateur a demandé le fichier). |

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

**Inchangés :** les clés `localStorage` `delfos-siem` et `delfos-client` (pour conserver les réglages existants) et les commentaires de code internes.

**Mis à jour : valeurs de données L2/L3.** Les statuts de dossier (`En cours L2`, `Escaladé L3`), le niveau (`L2`/`L3`), le mode des analyses et les décisions renvoyées par l'IA (`Rester en L2`, `Escalader en L3`) sont des valeurs **enregistrées** dans les dossiers existants et utilisées pour filtrer : les renommer casserait ces dossiers. Elles sont donc conservées telles quelles en base, et **affichées** en N2/N3 par une fonction d'affichage `NN()` (sélecteurs de statut et de niveau, étiquettes de statut, indicateurs, analyses, rapports lisibles). Le schéma JSON demandé à l'IA n'est pas modifié.

## 6. Modules

### 6.1 Hunting par hypothèses

- Entrée : choix d'une tactique puis d'une technique, issues des règles de `R`/`NR` (champ `m`).
- Sortie par technique : hypothèse, explication, sources de données nécessaires, pistes d'investigation, faux positifs connus, recommandations N2/N3 de la règle, et les requêtes déjà portées par la règle. Mis à jour : chacune des 31 règles porte déjà une requête **AQL** (`q`) et une requête Elastic (`e`) ; Splunk (`sp`) et Sentinel (`kq`) sont affichées quand elles existent. Les tactiques sans règle (Discovery, Collection, Exfiltration, Impact) reçoivent une hypothèse générique et un **squelette AQL** à adapter. Tout AQL est marqué « à valider dans votre environnement ».
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

Mis à jour :

1. Le fichier source n'est pas modifié ; la version N2/N3 est générée dans `assistant-n2-n3/assistant-n2-n3.html`.
2. Le fichier est remis à l'utilisateur comme pièce jointe téléchargeable. **Aucun Artifact n'est publié.**
3. Commit(s) sur `claude/new-session-8c4szi` et push ; **pas de pull request**.
4. Ouvert hors de Claude (fichier local), l'application fonctionne en **mode référence** : les modules N3, l'investigation, le hunting, les rapports et le générateur AQL marchent ; l'assistant IA et les dossiers partagés ne sont actifs que lorsque la page est ouverte dans Claude (comportement d'origine, conservé).

## 10. Risques et points à vérifier à l'implémentation

- Le fichier appelle `claude.use("sample"|"db"|"user")`. Mis à jour : ce pont d'origine est conservé sans changement. Il n'a été testé qu'avec une **simulation** de cette API, pas dans le runtime réel de Claude : le premier usage réel de l'IA et des dossiers partagés reste à confirmer.
- Mis à jour : le journal d'un dossier affiche un `type` inconnu comme texte brut ; une étiquette « Parcours N3 » est ajoutée pour les notes `n3-*`.
- Le menu passe à 12 boutons : vérifier l'affichage mobile (barre horizontale défilable).
- Les modèles AQL dépendent de la version et de la configuration QRadar : toujours présentés comme « à valider ».

## 11. Hors périmètre

- Connexion à une console QRadar ou à toute API de threat intelligence.
- Exécution d'actions de réponse (blocage, isolement, désactivation).
- Réécriture du moteur de détection, d'extraction ou de la bibliothèque de règles existants.
- Autres SIEM que ceux déjà gérés par le réglage SIEM actuel.

## 12. Extension (2026-11-18) : requêtes console Elasticsearch dans l'Alert Workflow

**Demande.** Ajouter, quand l'analyste colle une alerte, des requêtes de console (Kibana Dev Tools) du style `GET index-AAAA.MM.JJ,…/_search?size=0&format=yaml&filter_path=aggregations.*.buckets` avec un corps JSON (filtre `range` + `term`, agrégations `terms`). Emplacement précisé par l'utilisateur : **Alert Workflow** (et non l'onglet Investigation).

**Ce qui a été fait** (carte « Requêtes console Dev Tools (Elasticsearch) », après « Requêtes de pivot ») :

- **Index et plage.** Les index journaliers sont déduits de la ligne `Index:` de l'alerte (`base-AAAA.MM.JJ`, un par jour UTC couvert). Plage = première occurrence −1 h → dernière +1 h. Un champ « décalage de l'heure de l'alerte par rapport à UTC » corrige le fuseau du SIEM. Sans heures dans l'alerte : fenêtre relative signalée. Index illisible : `<INDEX>` + avertissement. Plus de 14 jours : motif `base-*`.
- **Issues de l'alerte (toutes familles).** Volume dans le temps (`date_histogram`), répartition par champs clés, aperçu de 20 événements, baseline sur 7 jours. Les critères de la règle (`IS`, `IS_NOT`, `IS_ONE_OF`, `IS_NOT_ONE_OF`, champs avec points) sont convertis en `filter` / `must_not`. Une partie contenant `OR` ou un opérateur non géré n'est jamais convertie en silence : une note l'indique.
- **Pivot sur une entité** (compte, IP, hôte, préremplie depuis l'alerte), fenêtre de 24 h avant la première occurrence à 1 h après la dernière. Active Directory (`winlog.*`) : postes NTLM 4776 (le cas de l'utilisateur), échecs 4625, sessions 4624, Kerberos 4768/4769, verrouillages 4740, modifications de compte. CEF : communications, volume sortant (`bytesOut`), URL. Pour toutes : première et dernière occurrence sur 30 jours.
- **Famille d'index** déduite du nom de l'index et des champs (`-ad`/`winlog` → AD ; `cef`/`sourceAddress`… → CEF ; sinon générique).
- **Copie** par requête ou « Copier toutes les requêtes » (titres en commentaires `#`).
- **Sécurité.** Le contenu de l'alerte est non fiable : valeurs insérées via `JSON.stringify` et `esc()`, nom d'index validé (`[A-Za-z0-9._*,-]`). Rien n'est exécuté ni envoyé.

**Correctifs apportés à l'existant** (présents dans le fichier d'origine) :

1. Deux fonctions `upd` coexistaient (Alert Workflow et dossiers) : la seconde écrasait la première, si bien que le verdict et le ticket de l'Alert Workflow ne se mettaient jamais à jour. Celle de l'Alert Workflow est renommée `awUpd`.
2. Le KQL/Lucene de la règle ne reconnaissait pas les champs contenant un point (`winlog.event_id`) : « Critère non reconnu ». Corrigé.
3. Le champ « Field to investigate » est lu en entier même avec des points (il était tronqué à `winlog`), et les valeurs impliquées (comptes, hôtes) sont lues en plus des IP.

**Limites.** Les requêtes sont générées, **pas exécutées** : aucun cluster Elasticsearch n'a été interrogé. Les noms de champs (`winlog.*` usuels, CEF) et le type des champs (`keyword` ou `ip`) dépendent de votre mapping ; un CIDR dans `terms` n'est valable que sur un champ de type `ip`. Les requêtes valident comme JSON et leur structure suit l'exemple fourni.

## 13. Extension (2026-11-18) : analyse du résultat d'une requête console dans l'Investigation

**Demande.** L'Investigation doit pouvoir analyser le résultat du `GET` exécuté depuis l'Alert Workflow.

**Parcours.** Dans chaque requête console de l'Alert Workflow, un bouton « Analyser le résultat » ouvre l'Investigation avec un bandeau (alerte, requête attendue). L'analyste colle la réponse de Dev Tools et clique sur « Analyser » : le texte est reconnu automatiquement, sans changer l'analyse des journaux existante.

**Formats reconnus.** Réponse `_search` en **YAML** (`format=yaml`) ou en **JSON** (y compris compact sur une ligne) ; plusieurs résultats collés à la suite (séparés par `---` ou objets JSON successifs) ; corps de requête JSON collé avant le résultat (ignoré, signalé) ; lignes `GET …` et commentaires `#` ignorés. Un texte illisible produit un message d'erreur, jamais une exception. Un journal ordinaire contenant « hits: » n'est pas détourné (la détection exige une structure Elasticsearch valide).

**Lecteur YAML.** Sous-ensemble écrit pour la sortie d'Elasticsearch (mappings, séquences au même retrait que leur clé, guillemets, échappements, blocs `|`/`>`, nombres en notation scientifique, `[]`/`{}`, `null`). Vérifié identique à PyYAML sur 11 échantillons au style Jackson.

**Analyse (règles déterministes, locales).** Reconnaissance du rôle de chaque agrégation par son nom (poste, compte, ip_source, statut, type_session, ports, actions, urls, volume, par_jour, premier/dernier…) ou par la forme des valeurs. Constats classés High / Medium / Info : IP publiques (étiquetées), sources nombreuses et diffuses, concentration, noms de machines évoquant un outil d'attaque ou par défaut, machines rares, comptes à privilèges, statuts d'échec NT décodés (mots de passe incorrects, comptes inexistants, verrouillés), types de session (8 et 9, sessions 3/10 depuis une IP publique), événements de gestion de compte, ports sensibles, trafic autorisé ou bloqué, URL suspectes, volume sortant (Medium à 10 Mo, High à 500 Mo), forme de la série temporelle (cadence régulière, pic isolé), baseline par jour, première et dernière occurrence comparées au début de l'alerte, écart avec le nombre d'événements annoncé par la règle (indice de mauvais index, plage ou fuseau). Les seuils sont des heuristiques à ajuster.

**Rendu et suites.** Verdict provisoire, constats, tableau par agrégation (part, décodage, sous-agrégations), graphiques de séries, échantillon d'événements avec renvoi vers le moteur de détection, **pivots suivants** (requêtes Dev Tools générées avec l'index et la plage de l'alerte : IP publique, compte, poste rare), copie de la synthèse Markdown, enregistrement dans le journal du dossier (type `es`), onglets Reports et IOC alimentés. Le bouton « Demander à l'assistant » (sur demande, avec les résultats résumés, les constats et le dossier ouvert) reprend les garde-fous de l'assistant existant (faits / hypothèses / non vérifié, données non fiables, aucune action exécutée).

**Limites.** Aucune réponse Elasticsearch réelle n'a été testée : les échantillons suivent le format produit avec `format=yaml`. Les agrégats orientent l'investigation mais ne prouvent pas une compromission. Les parts sont calculées sur les valeurs retournées (le `size` de la requête borne l'échantillon).

## 14. Extension (2026-11-20) : suivi des alertes, sauvegarde des résultats et section Ticket

**Demande.** (1) L'analyse du résultat d'une requête console n'était pas sauvegardée, alors qu'elle sert à rédiger le ticket. (2) Ajouter une section Ticket au format d'un exemple fourni (« Hello Team CLIENT, » + paragraphe + `=== Détails ===` + `=== Recommandations ===` + ligne des captures).

**Suivi des alertes en cours.** Chaque alerte analysée dans l'Alert Workflow est suivie automatiquement et sauvegardée dans le `localStorage` du navigateur (clé `assistant-n2n3-suivi`) : texte de l'alerte, verdict, hôtes impactés, constats, cases de vérification, réglages de la console (décalage, entité), résultats analysés et ticket. L'identité d'une alerte est un hachage de la règle, de l'index, de la plage, du nombre d'événements, des critères, du champ et des valeurs impliquées (deux alertes qui ne diffèrent que par l'entité restent distinctes). Une carte « Alertes en cours de traitement » liste les alertes (sévérité, verdict, nombre de résultats, dernière mise à jour) avec **Reprendre** (restaure tout l'état), **Supprimer** (en deux temps), **Exporter le suivi** (fichier JSON), **Copier le JSON** et **Importer**. Les données importées ou relues sont reconstruites champ par champ (types, longueurs, valeurs autorisées) ; les noms de clé non conformes (`__proto__`, etc.) sont refusés. Limites : 40 alertes, 15 résultats par alerte, 15 000 caractères de résultat brut par résultat. En cas de quota dépassé, les résultats bruts les plus anciens sont libérés, puis les alertes les plus anciennes (jamais l'alerte active). Si le stockage est indisponible, le suivi fonctionne en mémoire pour la session et le signale. Le suivi est propre à chaque navigateur : il n'est pas partagé entre analystes (la base partagée des dossiers n'est pas utilisée).

**Résultats sauvegardés.** Chaque analyse d'un résultat Elasticsearch dans l'Investigation est enregistrée automatiquement dans le suivi de l'alerte active (titre de la requête d'origine, requête, constats avec leur recommandation, valeurs principales par agrégation, synthèse, résultat brut). Le même résultat ré-analysé est mis à jour et non dupliqué. Sans alerte active, rien n'est écrit : un message explicite et un bouton permettent de sauvegarder après l'analyse de l'alerte. La carte « Résultats analysés » de l'Alert Workflow permet d'inclure ou non chaque résultat dans le ticket (et son résultat brut), de copier la requête, la synthèse ou le brut, et de supprimer. Le ticket interne (étape 5, avec export PDF) reprend les résultats inclus : requête (GET + corps JSON sur une ligne), constats, valeurs principales.

**Section Ticket (étape 6, message au client).** Format : `Hello Team <CLIENT>,` / paragraphe d'introduction / `=== Détails ===` (puces `•`) / `=== Recommandations ===` (numérotées) / `Captures jointes (onglet Fichiers) : …` (omise si vide). Trois zones sont préremplies automatiquement : l'**introduction** (période `jj/mm` et heures, nombre d'événements annoncés, règle sans son préfixe, entité, principaux constats, plus un marqueur `[À compléter : …]` signalé par un avertissement), les **détails** (une puce par valeur des agrégations sauvegardées : volume, étiquette d'IP publique, statuts décodés ; sinon règle, période et entités de l'alerte) et les **recommandations** (une par constat reconnu, triées par gravité, dédupliquées ; deux recommandations génériques si peu de constats). Le nom du client est déduit de l'index `customerlog-<prestataire>-<client>-<source>` (3e élément) et reste modifiable. Une zone modifiée à la main passe en « modifié » et n'est plus écrasée ; « Régénérer » la remet en automatique. La saisie accepte les puces ou numéros déjà présents. Le bouton « Rédiger avec l'assistant » (sur demande, avec l'alerte, les résultats inclus et le brouillon) impose ce format et **un exemple fictif** : l'exemple réel de l'utilisateur n'est pas embarqué dans le fichier. La réponse est découpée dans les zones, la ligne « Captures jointes » de l'IA est ignorée, et un message demande de relire avant envoi. Le ticket n'est jamais envoyé par l'outil : il se copie.

**Correctifs.** Le motif de la recommandation « isoler la machine » ne s'applique plus au constat « nom de machine par défaut » (son libellé citait « outil d'attaque »). La clé d'alerte inclut critères et valeurs.

**Limites.** Les brouillons sont factuels et à relire : l'interprétation (cause, absence d'authentification réussie, cycle d'un poste, etc.) reste le travail de l'analyste ; les recommandations viennent d'une table de règles locale, pas d'une analyse de votre contexte. La rédaction par l'assistant n'a été testée qu'avec une simulation de l'API Claude, pas dans le runtime réel.
