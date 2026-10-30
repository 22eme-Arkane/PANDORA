## 2.7.0 · 2026-10-27

**PANDORA en noir, la dictée vocale d'ORAKLE dans tous les champs, un nouveau
logo, vos propres machines pour calculer — et les nouveautés de chaque version
directement dans PANDORA.**

- **PANDORA s'ouvre en noir.** Le nouveau thème **Noir** garde les couleurs de
  PANDORA (turquoise, violet) sur un fond noir, page d'accueil comprise.
  Paramètres → Général → Apparence propose un menu déroulant avec un aperçu de
  chaque thème : **Noir**, **Nuit bleue** (le bleu sombre d'origine) et **Clair**.
  Le thème choisi s'applique au redémarrage, et PANDORA propose de redémarrer
  tout de suite.
- **La dictée vocale d'ORAKLE.** Un petit micro apparaît dans les champs où l'on
  écrit : cliquez, parlez, recliquez — le texte s'écrit au curseur. Raccourcis
  d'ORAKLE dans un champ : **Ctrl+1 maintenu** (on parle tant qu'il est enfoncé),
  **Ctrl+1 deux fois** (mains libres, Ctrl+1 pour écrire), **Échap** pour annuler.
  Tout se calcule sur cet ordinateur ; si ORAKLE est installé, son dictionnaire et
  son modèle servent aussi à PANDORA. Le modèle Whisper (≈ 480 Mo) se télécharge
  une seule fois, avec votre accord. Paramètres → Général → Dictée vocale masque
  les micros.
- **Un nouveau logo.** L'icône de l'application, de la barre des tâches et de
  l'installeur change ; en haut de la fenêtre, le nom PANDORA reste seul, centré.
- **Un nouveau fond pour la page de démarrage** : noir, parcouru de circuits
  dorés, assorti au nouveau logo.
- **Un installeur plus moderne**, sombre, aux couleurs du nouveau logo, avec une
  page d'accueil.
- **Les nouveautés dans l'application.** À la première ouverture ou création d'un
  projet après une mise à jour, cette fenêtre présente les nouveautés de la version
  et l'historique des précédentes. La case « Ne plus afficher jusqu'à la prochaine
  version » la range jusqu'à la mise à jour suivante ; Paramètres → « Nouveautés »
  la rouvre à tout moment.
- **AIODOS — calculer sur mes machines.** Si AIODOS est installé, PANDORA peut
  envoyer les gabarits ComfyUI (images, vidéos, modification de clips) à vos
  machines au lieu de ce seul PC, et utiliser les modèles de conversation d'AIODOS
  comme IA texte. Tout se règle dans Paramètres → AIODOS ; rien ne part sur une
  autre machine sans votre choix.
- **Un onglet « AIODOS »** montre les machines connectées et les travaux en cours,
  avec Pause, Reprendre, Annuler, Relancer les échecs et Oublier. Dans le Studio IA,
  un panneau pliable en bas liste les machines qui calculent, à la manière des
  pairs d'un client BitTorrent — il n'apparaît que lorsque le calcul passe par
  AIODOS.
- **Un onglet « 3D » remplace le Plan de feu.** Chaque plan a sa scène en trois
  dimensions, à l'échelle réelle : la vue 3D d'ARKLIGHT, avec ses vrais projecteurs
  (ARRI, Aputure, Astera, HMI, tungstène…), son grip, ses meubles, ses véhicules et
  des mannequins pour les personnages. L'onglet s'ouvre en vue Perspective ; le
  bouton « Caméra » montre exactement ce que filme la caméra, avec sa focale.
  L'ancien plan de feu de chaque plan est repris automatiquement, et le plan du
  décor est posé au sol.
- **L'inspecteur complet d'ARKLIGHT pour les projecteurs.** Dans le panneau de droite,
  un projecteur sélectionné montre ses commandes (face avant du modèle simulée :
  écran, touches, molettes, menus — ARRI, Aputure, Astera, DMG, Kino Flo, LiteGear,
  Hive, Dedolight…), ses réglages, son état simulé, sa position, puis accessoires
  et zoom. Le prompt décrit la lumière que le projecteur émet vraiment, quel que
  soit le réglage utilisé.
- **Des keyframes pour chaque élément.** Personnages, caméra, mobilier, animaux,
  véhicules : chacun a ses propres keyframes sur la frise, qu'on déplace à la souris.
  Les personnages sont des mannequins articulés qui marchent, courent, s'assoient,
  parlent, se battent… (plus de 40 actions) : chaque keyframe a son action (avancer,
  puis un mouvement de combat, puis courir). La caméra se déplace dans tous les
  sens, monte et descend sur son pied, pivote, et tout cela s'écrit dans le prompt.
  La durée du plan se règle dans la frise, jusqu'à 30 s avec Seedance 2.5. Un mouvement
  de caméra du storyboard (travelling arrière…) arrive déjà en keyframes. Espace lance
  la lecture, Suppr retire la keyframe, le clic droit ajoute un élément à cet endroit,
  et « Cadrer le personnage » tourne la caméra ou le projecteur vers lui.
- **Le prompt ne change plus tout seul.** Le panneau de droite montre le texte de la
  scène ; « Inscrire dans le storyboard » l'écrit pour ce plan, et le menu Action
  le fait pour tous les plans. Le mobilier et les éléments de décor posés y figurent.
- **La mise en scène par l'IA.** « ✦ Mise en scène par l'IA » : décrivez l'action du
  plan en mots (« Léa entre par la droite, s'assoit et parle ; Paul se lève à la
  fin »), l'IA pose les keyframes sur la frise, vous ajustez dans la vue ;
  « Revenir aux keyframes d'avant » annule. Tâche réglable dans Paramètres.
- **Exporter la vidéo, référence pour Seedance.** Menu Action → « 🎬 Exporter la
  vidéo » rend le plan vu par sa caméra, avec la mise en scène (1280×720, sans aucun
  projecteur à l'image). Dans le Studio IA, RENDU & AUDIO → « Prévisualisation de la
  vue 3D » (décochée par défaut) l'envoie à Seedance comme vidéo de référence : il
  en suit la caméra, le cadre et la place des personnages. Ses secondes sont
  facturées en plus du plan.
- **Le prompt écrit d'après la scène.** Les sections Mise en scène et Plan de feu
  disent où sont les personnages dans le cadre et comment ils se présentent à la
  caméra, d'où vient chaque lumière vue de la caméra, si elle est douce ou dure, sa
  couleur, sa force réelle sur le visage et le contraste qui en résulte ; l'axe, la
  distance, la hauteur et la focale du plan suivent. Les déplacements et
  les actions de la frise s'écrivent minutés (« de 0 s à 2,2 s marche, entre dans
  le champ par la gauche, puis s'assoit »), et le mouvement de caméra aussi. Le texte écrit est affiché à
  droite de la vue.
- **Décors** : l'atelier « 7 vues », qui ne donnait pas de bons résultats, est
  retiré ; la génération classique et le plan du décor restent. La bande « Plan
  des décors » est repliée par défaut.
- **Castings, Décors, Accessoires, HMC, Véhicules** : le panneau « FICHE » est
  ouvert par défaut, et les vignettes occupent toute la largeur (elles
  s'arrêtaient à trois par ligne, avec un grand vide à droite).
- **ComfyUI tient en une seule entrée.** La longue liste des gabarits ComfyUI dans
  les menus de moteurs est remplacée par UNE entrée « ComfyUI », suivie de deux
  menus : « Moteur IA » et « Calcul » (Ce PC, Mes machines · AIODOS ou Réseau
  public · AIODOS). Les moteurs sont rangés par famille de modèles, un trait entre
  chaque famille, du plus performant au moins performant du marché. Le dernier
  choisi est retenu.
- **Le réseau public d'AIODOS.** Coché dans l'onglet AIODOS, il devient le
  « Calcul » proposé par défaut. Une image de référence ou un clip reste toujours
  sur ce PC et vos machines.
- **L'onglet AIODOS à part**, dans la barre du bas, juste après Studio IA. S'il
  n'est pas installé, l'onglet le présente et propose de l'installer. Dans le
  Studio IA, le panneau des machines connectées reste replié — un clic sur son
  en-tête le déplie ; déplié, il ne prend que la place de son contenu.
- **Coller sans fond blanc.** Un texte collé depuis un navigateur ou un traitement
  de texte perd son fond et sa couleur ; le bouton « Retirer le fond » des outils
  de texte les retire d'un texte déjà collé.
- **FilmCraft relié à PANDORA.** Le logiciel de montage de la suite ArtCraft
  reçoit automatiquement chaque clip généré (chutier PANDORA, un sous-chutier par
  séquence), comme DaVinci Resolve ; Storyboard → Action → « Monter dans
  FilmCraft » y monte la dernière prise de chaque plan. Paramètres → FilmCraft :
  « Ouvrir FilmCraft relié à PANDORA ».
- **Barre du bas** : les onglets au centre, « Coût du projet » à gauche, AIODOS et
  Paramètres à droite. La langue se choisit dans Paramètres → Général → Langue.
- **Storyboard** : le menu « Prompt » passe à côté d'« Action ».
- **PANDORA passe sous licence Apache 2.0** : libre d'utiliser, modifier et
  redistribuer PANDORA, y compris commercialement, en gardant la licence et le
  fichier NOTICE.
- **Corrections.** Le redimensionnement d'une colonne du storyboard pouvait, dans
  de rares cas, fermer PANDORA sans message après la reconstruction du tableau ;
  même chose pour le défilement différé de la discussion d'une fiche. Corrigé dans
  les deux éditions. Fermer la fenêtre Mood ouverte depuis le Storyboard pouvait
  aussi fermer PANDORA : corrigé.

## 2.6.1 · 2026-10-05

**Des distributeurs qui disent ce qui ne va pas — et des références de personnages
que Seedance arrive enfin à lire.**

- **Références de personnages acceptées par BytePlus.** PANDORA regroupe les
  personnages d'un plan dans une mosaïque légendée en cases de 210 × 260 ; BytePlus
  refusait d'emblée un personnage seul (« image pixel count must be ≥ 90000 »).
  Toute image envoyée à BytePlus, Runware ou PiAPI est désormais ramenée dans les
  limites de Seedance (300 à 6000 px par côté, rapport largeur/hauteur de 0,4 à 2,5)
  en la cadrant sur un fond neutre — jamais en l'agrandissant : des cases plus
  grandes, essayées en premier, ont fait refuser par le propriétaire de Seedance tous
  les plans avec un personnage (« real people's faces »), chez BytePlus comme chez
  fal.ai. Une image déjà dans les limites part telle quelle.
- **BytePlus : une clé valide ne suffit pas.** Chaque modèle Seedance doit être activé
  dans la console BytePlus, ce qui exige au moins 30 $ de crédit. Le test de clé
  vérifie désormais aussi les modèles (« Clé acceptée — modèles à activer »), le menu
  des distributeurs du Studio affiche « Seedance non activé », et l'ordre de priorité
  saute BytePlus pour un moteur non activé, en disant pourquoi.
- **Runware sans crédit** est signalé clairement (au moins 5 $ de crédit), et les plans
  suivants partent chez le distributeur suivant.
- **Un VPN qui coupe la connexion est nommé.** Une connexion réinitialisée en pleine
  requête (ConnectionResetError 10054) s'affichait « BytePlus injoignable ». PANDORA
  détecte maintenant un VPN actif sur l'ordinateur (NordVPN, WireGuard, OpenVPN,
  Proton…) et le dit, avec la solution : le couper pendant les générations, ou exclure
  PANDORA du VPN (split tunneling). Même conseil pour fal.ai et l'IA texte.
- **Réessayer avec un autre distributeur.** Une génération en échec ouvre désormais UNE
  seule fenêtre (il y en avait deux à la suite), avec un bouton par distributeur
  capable de faire le plan et le prix qu'il y coûte. Rien ne bascule tout seul : vous
  choisissez, le distributeur passe en tête de l'ordre, et la file repart du plan en
  échec. Pas de bouton quand le refus vient du filtre du propriétaire du modèle (vrais
  visages, droits d'auteur) : il est le même chez tous les distributeurs.
- **Reprendre un plan : même prompt, même seed.** « ↻ Reprendre » (Historique et
  Vidéothèque) ne ramenait que le prompt de travail — de nouveau réécrit par l'IA à
  l'envoi — et une seed qui n'arrivait jamais chez BytePlus. Il restaure maintenant le
  prompt exact qui avait été envoyé (renvoyé mot pour mot), les réglages du plan et sa
  seed. La seed ne part que là où le moteur la lit — BytePlus pour Seedance 2.5, fal
  uniquement en mode référence — et le Studio le précise sous « ADN visuel ». Même
  avec la même seed, ByteDance promet un résultat proche, pas identique.
- **« ⊘ Aucun » dans tous les menus du storyboard** (mouvement de caméra, valeur de
  plan, focale, optique, vitesse, axe, heure — et musique et transition dans PANDORA
  Live) : le champ reste vide et rien n'est injecté dans le prompt à sa place.
- **« ⊘ Aucun style » pour le film** (page Scénario) : aucun style n'est ajouté aux
  prompts — ni un style du catalogue, ni la note de réalisation, qui transportait
  aussi le boîtier caméra, les mouvements de caméra et le rythme de montage dans
  chaque plan.
- **Les prompts de plus de 4 000 caractères évitent PiAPI**, dont c'est la limite, avec
  la raison affichée ; BytePlus et fal.ai acceptent des prompts plus longs. Et la
  réécriture du prompt ne reçoit plus « Grue / Drone » tel quel : elle écrivait
  « drone/crane move », et Seedance dessinait un drone.

## 2.6.0 · 2026-10-04

**Un DaVinci Resolve qui dit ce qui ne va pas, un export de timeline pour tout le
monde, votre forfait ChatGPT pour les tâches texte et un mode demi-tarif pour le
storyboard.**

- **Pont DaVinci Resolve v2.** Un import en échec restait silencieux ; PANDORA indique
  maintenant la vraie raison donnée par Resolve (fenêtre du pont fermée, version
  Studio requise, Python absent, script périmé, Resolve occupé) et l'aide dit quoi
  faire. Le test de connexion ne fige plus la fenêtre, et une deuxième fenêtre de pont
  prend le relais de la première au lieu d'échouer.
- **Des scripts que l'on peut réparer.** Les deux scripts Resolve sont versionnés :
  Paramètres → DaVinci Resolve indique s'ils sont absents ou périmés, et « Installer /
  mettre à jour les scripts » les écrit là où Resolve les cherche.
- **Clips rangés par séquence.** Chaque clip importé va dans le chutier de sa séquence
  (PANDORA/SQ03…) avec scène, plan, prise, action et la couleur de la séquence.
- **Monter le storyboard dans Resolve.** Storyboard → Action → « Monter dans DaVinci
  Resolve » construit une timeline à partir de la dernière prise de chaque plan, dans
  l'ordre du storyboard (Resolve Studio + pont).
- **Exporter la timeline (XML) — Resolve gratuit, Studio ou Premiere.** Storyboard →
  Action → « Exporter la timeline (XML) » écrit une timeline XML Final Cut Pro 7 : la
  dernière prise de chaque plan bout à bout, un marqueur par plan (séquence, plan,
  prise) avec son action en commentaire. Ni pont, ni plugin : Fichier → Importer →
  Timeline dans Resolve, Fichier → Importer dans Premiere. Aussi dans PANDORA Live.
- **Compte ChatGPT pour les tâches texte.** Dans Assistant IA, « Compte ChatGPT
  (forfait Plus / Pro) » utilise votre abonnement ChatGPT au lieu d'une clé API — pour
  toutes les tâches ou pour une seule. Vous vous connectez sur la page d'OpenAI dans
  votre navigateur ; les jetons restent sur votre ordinateur. Quand la limite du
  forfait est atteinte, PANDORA le met en pause et ne bascule jamais tout seul sur une
  clé payante, sauf si vous cochez cette option. Pour l'instant, OpenAI ferme la
  session au bout d'une heure : un clic vous reconnecte.
- **Mode économie — lots Claude (−50 %).** Une case dans Assistant IA envoie la
  génération du storyboard (conversion du découpage et prompts finaux) par les Message
  Batches d'Anthropic : moitié prix, résultats en général en quelques minutes (24 h au
  plus). La fenêtre affiche l'avancement, « Annuler » arrête aussi les lots chez
  Anthropic, et le coût du projet compte ces appels à moitié prix.
- **File du Studio.** Quand la recomposition automatique est désactivée, une file
  n'attend plus 90 secondes par plan un prompt qui ne viendra jamais ; pendant la
  préparation du prompt final d'un plan, la barre de progression l'indique au lieu de
  rester cachée.
- **Le vrai distributeur est annoncé.** Lancer une file affichait « crédits fal.ai »
  même quand PiAPI, BytePlus ou Runware servaient les plans : le message nomme
  maintenant le distributeur qui les facture, ou précise qu'un moteur local ne coûte
  rien. Pareil dans « Modifier des clips ».
- **Des mouvements aériens sans le mot « drone ».** « Grue / Drone » et « Drone FPV »
  écrivaient « drone » dans le prompt, et les moteurs en dessinaient parfois un dans le
  plan. Ils décrivent désormais le vol lui-même (sweeping aerial move,
  first-person-view flight).

## 2.5.0 · 2026-10-04

**Seedance jusqu'à moitié prix, avec les distributeurs de votre choix — et une page
Paramètres plus claire.**

- **Distributeurs vidéo low cost : BytePlus, Runware, PiAPI (désormais avec Seedance
  2.5).** Le moteur est le même partout (Seedance, de ByteDance), seul le prix change :
  un plan Seedance 2.5 de 30 secondes en 720p coûte environ 14,19 $ chez fal.ai,
  6,93 $ HT chez BytePlus (revendeur officiel de ByteDance), 6,90 $ chez Runware et
  10,50 $ chez PiAPI. Chaque distributeur a sa clé, un test de clé gratuit et un lien
  « Obtenir une clé ».
- **Un ordre de priorité avec bascule automatique.** Dans Paramètres → Distribution des
  vidéos, vous cochez les distributeurs voulus et vous les classez. Pour chaque plan,
  PANDORA prend le premier capable de le faire — moteur, résolution, son coupé, image
  de début / fin, réception de vos images de référence — sinon il passe au suivant et
  la progression dit pourquoi (« PiAPI ne peut pas recevoir de fichiers → BytePlus »).
  Un compte fal.ai bloqué faute de solde est sauté. Le mode Mono-distributeur ne garde
  que le premier, sans bascule.
- **Vos images ne dépendent plus de fal.ai.** PANDORA téléversait toutes les images de
  référence (personnages, décor, mood) sur le stockage de fal, même pour un autre
  distributeur : avec un compte fal bloqué, le mood n'arrivait jamais chez PiAPI et le
  plan était généré — et facturé — sans lui. Les fichiers passent désormais par le
  canal propre à chaque distributeur (dans la requête pour BytePlus et Runware, par le
  téléversement de PiAPI sinon), et un plan dont les images ne peuvent pas partir
  s'arrête avant l'appel payant, avec la vraie raison.
- **Menu des distributeurs dans le Studio**, à côté du moteur de génération : le prix du
  plan en cours chez chaque distributeur ; en choisir un le place en tête. Le menu
  Résolution affiche le prix du distributeur qui servira le plan, et les options
  qu'aucun distributeur activé ne sait faire sont grisées, avec la raison.
- **Paramètres réorganisés** en six sections repliables — Général, Assistant IA, Clés
  API, Distribution des vidéos, DaVinci Resolve Studio, Paramètres avancés (MiniMax H3
  en local, ComfyUI, modules externes) — dont chaque en-tête montre l'état d'un coup
  d'œil.
- **Guide de démarrage** : une nouvelle étape facultative pour ajouter une clé de
  distributeur low cost, avec ce à quoi sert chacun et ce qu'il coûte. L'étape des
  crédits fal.ai ne promet plus « 20 à 50 vidéos pour 10 $ » (une vidéo Seedance 2.0 de
  10 secondes en 720p coûte environ 3 $ chez fal.ai).
- **Storyboard : un seul menu « Prompt »** à côté du nombre de plans remplace la
  bascule structuré / final et le sélecteur de forme de prompt.
- **Recomposer à la demande.** La fenêtre Mood et le Studio reçoivent un bouton
  « Recomposer le prompt » et une case « Recomposer automatiquement », mémorisée une
  fois pour toutes : décochez-la et aucune réécriture IA ne se lance à l'affichage d'un
  plan ; un prompt déjà composé reste affiché.
- Coût réel journalisé quand le distributeur le renvoie (tokens BytePlus, coût
  Runware) ; le coût du projet utilise le prix du distributeur qui a réellement servi
  le plan.

## 2.4.2 · 2026-10-03

**Changez le décor derrière vos acteurs sans toucher à leurs visages — et tous les
modèles Claude sont à jour.**

- **« Changer le décor · acteurs intacts » (Modifier des clips, deux éditions).**
  Seedance refuse la plupart des clips qui montrent des visages réalistes : c'est le
  filtre de ByteDance (`partner_validation_failed`), le même chez tous les
  distributeurs — fal.ai n'y est pour rien. Ce nouveau moteur ne fait passer vos
  acteurs par aucun modèle génératif : VEED les détoure, un décor vide de toute
  présence est créé (une image générée à partir de votre consigne, une vidéo
  Seedance 2.0, votre image de référence telle quelle, ou votre propre fichier image ou
  vidéo), et PANDORA y recompose les acteurs sur votre machine — visages, lèvres et son
  identiques au clip source (mesuré : aucune différence de pixel sur les acteurs).
  Options : accorder la couleur des acteurs au décor (en local, gratuit) et un
  rééclairage IA ID-V2V expérimental. Le panneau annonce les limites : les ombres
  portées disparaissent, et le décor ne suit pas un mouvement de caméra.
- **La file s'arrête au premier refus du filtre de contenu**, en nommant le moteur et
  la vraie raison, au lieu de payer le même refus sur chacun des clips suivants ;
  choisir Seedance dans « Modifier des clips » affiche d'emblée l'avertissement sur les
  visages.
- **Modèles Claude mis à jour : Opus 5.5, Sonnet 5.5 et Fable 5.1** (Haiku 4.5 reste
  le Haiku le plus récent), dans les deux éditions. Les nouveaux modèles refusent le
  réglage « réflexion désactivée » que PANDORA envoyait à tous les modèles Claude, si
  bien que tous les appels texte auraient échoué : réflexion, effort et marge de sortie
  sont désormais réglés par modèle — Opus 5.5 à son effort le plus bas avec de la place
  pour sa réflexion, Sonnet 5.5 sans réflexion étendue comme avant. Les choix
  enregistrés qui désignent un ancien modèle passent à son successeur, et les modèles
  remplacés ne sont plus listés. Quand un filtre de sécurité d'Anthropic décline une
  requête, PANDORA dit quel modèle a décliné et pourquoi au lieu de renvoyer un texte
  vide, et Anthropic relance certaines catégories sur un autre modèle. Vérifié par un
  vrai appel minimal par modèle.
- **Coût du projet : l'IA texte au bon prix.** Le journal comptait Opus 4.8 trois fois
  trop cher et Sonnet 5 une fois et demie trop cher ; il suit maintenant la grille
  tarifaire actuelle d'Anthropic (Opus 5.5 est d'ailleurs moins cher qu'Opus 4.8).
- **Plans de plus de 15 s quand le projet vise Seedance 2.5.** La fenêtre du plan
  proposait déjà 30 s, mais chaque enregistrement ramenait le plan à 15 s, le découpage
  rejetait toute fiche au-delà de 15 s, et les consignes du storyboard l'interdisaient.
  La limite suit désormais le moteur cible partout — découpage, co-écriture,
  storyboard, case Durée, fenêtre du plan et Studio, à partir d'une seule table : 30 s
  pour Seedance 2.5 et Wan 3.0, 20 s pour Sora 2 et Flux 3, 15 s pour les autres.
  « Générer depuis Storyboard » s'ouvre maintenant sur le moteur cible du projet, relit
  la durée du plan quand vous changez de moteur (un plan de 30 s restait à 15 s après
  le passage de Seedance 2.0 à 2.5), et chiffre la durée réellement envoyée.
- **Les refus disent pourquoi.** Un clip refusé par le filtre de ByteDance nomme
  maintenant la vraie raison : Seedance 2.5 avait rejeté une vidéo terminée pour
  *possible copyright resemblance*, et PANDORA annonçait « contenu violent ou
  explicite ». La ligne de progression nomme désormais le moteur réellement appelé
  (elle affichait toujours « Seedance 2.0 », même quand Seedance 2.5 faisait le rendu).
- **Migration des réglages enfin enregistrée.** La mise à jour unique des réglages
  enregistrés s'exécutait alors que config.json était encore ouvert, ce que Windows
  refuse : elle n'atteignait jamais le disque, et un config.json.tmp était réécrit à
  chaque lecture.

## 2.4.1 · 2026-09-26

**Tous les moteurs du Studio Images fonctionnent à nouveau, et le Studio appartient
désormais à votre projet.**

- **Studio Images : tous les moteurs réparés.** Depuis la v2.4.0, tous les moteurs
  d'image du Studio (Seedream, Recraft, Nano Banana, Ideogram, Recraft Vector…) et
  Outpaint s'arrêtaient sur « maximum recursion depth exceeded » : en faisant passer
  les appels par un point d'entrée unique fal/ComfyUI, la fonction qui envoie vers fal
  s'était mise à s'appeler elle-même. Corrigé, avec un test qui parcourt le vrai chemin
  d'appel (l'ancien test ne lisait que le texte du code, et avait laissé passer
  l'erreur).
- **L'état du Studio suit le projet.** Le prompt, les images de référence, la
  discussion avec Claude, la dernière image et les réglages sont enregistrés dans le
  projet lui-même (`data/Image IA/`) à chaque modification et reviennent à la
  réouverture du projet — ils étaient perdus auparavant. Ouvrir un autre projet
  n'emporte plus les images de référence du précédent ; les références importées sont
  copiées dans le projet, elles voyagent donc avec lui.
- **Les messages de la discussion se copient.** Cliquez sur un message et appuyez sur
  Ctrl+C pour le copier en entier (ou seulement la partie sélectionnée), ou clic droit
  → « Copier le message ». Avant, le clic ne donnait pas le focus clavier au message,
  et Ctrl+C ne copiait rien.
- **« Générer avec plusieurs moteurs » mémorise votre sélection** — dans chaque projet
  et après un redémarrage — au lieu de revenir à un moteur par famille.
- **« Modifier des clips » : le bon compte est mis en cause, le clip est adapté au
  moteur, et le lip-sync est à jour.** Une modification en échec était signalée
  « Crédits fal.ai insuffisants » quelle qu'en soit la cause : le détecteur de crédit
  réagissait à des mots comme « balance », « credit », « out of » ou « quota », si bien
  qu'un compte *Anthropic* vide (traduction) ou une erreur de validation fal
  (« duration out of range ») portait la même étiquette. Chaque message nomme désormais
  son compte, et la raison donnée par fal est affichée. Le clip source est converti
  dans ce que le moteur accepte avant le téléversement (Seedance 2.0 : 720p et 15 s ;
  un export en 1080p était refusé). Veo 3.1 est envoyé avec la tolérance de modération
  maximale. La ligne lip-sync de « Modifier des clips » reçoit le menu des moteurs
  (Sync-3, Kling, PixVerse, VEED, Sync 2, LatentSync — avec année et spécialité) et
  l'audio à synchroniser : la piste du clip lui-même ou un fichier de doublage, dans
  les deux éditions ; un clip rendu en local (ComfyUI) est téléversé avant la
  synchronisation.
- **Installeur.** L'image en haut à droite montre le logo actuel de PANDORA ; les cases
  à cocher de la dernière page sont dessinées en entier (elles étaient coupées à
  gauche — vérifié cette fois sur un vrai rendu à 150 %) ; « Voir le tutoriel
  complet » disparaît jusqu'à ce que le nouveau tutoriel soit prêt.

## 2.4.0 · 2026-09-24

**Votre propre machine devient un moteur de rendu — et un projet s'ouvre maintenant en
moins d'une seconde au lieu de quarante.**

- **ComfyUI comme moteur de rendu, et moteur local par défaut.** Trois moteurs
  rejoignent l'onglet Génération directe : *MiniMax H3 — texte vers vidéo* et *image
  vers vidéo* sur les gabarits officiels de ComfyUI, et *Workflow personnalisé* —
  n'importe quel `.json` enregistré depuis l'éditeur ComfyUI. PANDORA n'embarque rien
  de ComfyUI ni de MiniMax : il dialogue avec votre ComfyUI Desktop, convertit lui-même
  le workflow de l'éditeur au format API (sous-graphes, reroutes, primitives — vérifié
  nœud par nœud contre ce qu'envoie le frontend de ComfyUI), téléverse vos images, suit
  la file et rapporte le clip. Choisissez le moteur sans serveur lancé et une fenêtre
  vous guide pour l'installer ou le lancer. Avant tout envoi, une vérification
  préalable liste exactement les fichiers de modèle que ComfyUI ne voit pas et le
  dossier où va chacun. Vérifié de bout en bout : un clip de 5 secondes avec sa
  bande-son, sur le GPU de 8 Go d'un ordinateur portable. 0 $.
- **MiniMax H3 (Hailuo 3.0) sur fal.ai, trois paliers** — H3, H3 Max, H3 Max Turbo —
  chiffrés par palier dans « Coût du projet », plus H3 *en local* via un serveur
  stable-diffusion.cpp conçu pour les cartes de 8 Go. La licence du modèle exclut
  certains territoires ; PANDORA affiche l'avis, le choix vous appartient.
- **Ouverture d'un projet : 46 s → 0,4 s.** Chaque page et chaque onglet du Studio
  étaient construits d'emblée ; chacun l'est maintenant au premier clic. Les fenêtres
  fantômes qui s'ouvraient et se refermaient pendant le chargement ou la duplication
  d'un projet étaient cinq widgets affichés avant d'avoir un parent — disparues. Le
  Storyboard ne dessine plus son tableau deux fois à la première visite.
- **Descripteur de projet écrit de façon atomique — et réparé.** Un projet dont le
  descripteur avait été tronqué à 0 octet ne pouvait plus être ouvert ; il est
  maintenant reconstruit à partir de son dossier.
- **« Coût du projet » était faux pour huit moteurs vidéo.** Toute une famille était
  journalisée à 0,30 $/s quel que soit son vrai prix (le suffixe de mode la cachait à
  la grille tarifaire), quatre moteurs n'avaient aucun prix, et Hailuo 2.3 Pro est
  facturé au clip, pas à la seconde. Corrigé, avec un test de dérive.
- **La détection de ComfyUI tolère un GPU à froid** — le premier appel d'état après une
  pause prend plus d'une seconde ; un serveur en marche ne passe plus pour absent.
- **Modules externes : PANDORA installe ce qu'il n'embarque pas.** Choisissez un
  moteur qui a besoin de ComfyUI, du serveur H3 local ou d'Ollama, et un bandeau vous
  dit aussitôt ce qui manque ; une fenêtre explique les étapes et fait le travail en un
  clic — télécharge l'installeur officiel de ComfyUI Desktop ou d'Ollama et le lance,
  dépose les cinq fichiers de modèle MiniMax H3 (~45 Go, téléchargement reprenable)
  directement dans le dossier des modèles de ComfyUI, récupère le projet communautaire
  sd.cpp et lance son installation, télécharge un modèle Ollama, démarre ce qui est
  installé mais pas lancé. Les Paramètres reçoivent un tableau « Modules externes »
  avec l'état de chacun. Rien n'est téléchargé ni lancé sans un clic.
- **H3 génère depuis le Storyboard.** MiniMax H3 (fal, sd.cpp en local, ComfyUI)
  apparaît désormais dans « Générer depuis Storyboard » et dans les séquences Live, pas
  seulement dans l'onglet Génération directe.
- **Chaque gabarit d'image ouvert de ComfyUI devient un moteur d'image — 0 $.**
  Personnages, décors, accessoires, moods et le Studio Images peuvent désormais faire
  leur rendu sur votre propre GPU : PANDORA lit l'index officiel des gabarits de
  ComfyUI (la catégorie « Image » — Z-Image, Flux.2 Klein et Dev, Qwen-Image et
  Qwen-Image-Edit, Krea-2, SDXL, SD3.5, HiDream, Chroma, Lumina, OmniGen2… 101 gabarits,
  jusqu'aux plus lourds), déduit de la structure même de chaque gabarit d'où il tire
  son prompt, son prompt négatif, sa taille, sa seed et ses images de référence, et
  l'appelle par le même chemin unique que les moteurs fal. La liste est lue auprès de
  votre ComfyUI et mise en cache : elle suit donc les mises à jour de ComfyUI. La
  fenêtre ComfyUI télécharge pour vous les fichiers de modèle d'un gabarit. Vérifié de
  bout en bout : une image SDXL en 16 s.
- **Les IA texte locales fonctionnent comme Claude.** Quatre choses empêchaient un
  modèle local de bien se comporter : Ollama coupait silencieusement l'*entrée*
  (aucune fenêtre de contexte n'était demandée, si bien qu'un scénario perdait son
  début et le prompt système), les modèles de raisonnement laissaient leurs blocs
  `<think>` dans la réponse (l'analyse du JSON cassait, le budget de sortie était
  dévoré), un modèle sans vision « décrivait » des images qu'il n'avait jamais vues, et
  LM Studio, llama.cpp, vLLM et Jan n'existaient que derrière « fournisseur
  personnalisé ». Désormais : la fenêtre de contexte est dimensionnée à chaque appel
  (plafond réglable), la réflexion est coupée quand le modèle le permet et filtrée
  sinon (réponses et flux, tous les moteurs hors Anthropic), une erreur claire propose
  un modèle doté de vision, et un groupe « Local — sur votre machine » dans l'Assistant
  IA propose Ollama et un *Serveur IA local* avec des préréglages pour LM Studio,
  llama.cpp, vLLM et Jan — adresse, découverte des modèles, fenêtre d'installation et
  de lancement. La fenêtre Ollama liste des modèles recommandés de 5 Go à 140 Go (Qwen,
  Gemma, Mistral, gpt-oss, Llama, DeepSeek) et les télécharge. La consommation de
  tokens de chaque moteur est journalisée dans « Coût du projet » (moteurs locaux à
  0 $). Un script de conformité (`tools/ai_conformance.py`) vérifie n'importe quel
  moteur au regard des vraies exigences de PANDORA : traduction brute, tableaux et
  objets JSON, marqueurs exacts, troncature + continuation, absence de réflexion,
  contexte long, vision.
- **« Modifier un clip » fonctionne à nouveau — et sur votre propre GPU.** Tous les
  vrais envois depuis « Modifier un clip » échouaient depuis la v2.2.0, dans les deux
  éditions : le code lisait une variable supprimée en août, après avoir transcodé le
  clip et payé la traduction. Corrigé, avec un test qui lit les noms propres à la
  fonction. Également corrigé lors de l'audit : « Annuler » laissait derrière lui un
  thread actif (un plantage quelques secondes plus tard), la résolution par défaut
  était la 4K (cinq fois le prix du 720p), l'édition Live ignorait l'interrupteur
  audio, affichait « ✓ » sur un téléchargement raté et ne journalisait ni historique
  ni coût, un clip source manquant devenait silencieusement une génération à partir du
  seul texte, et des images de référence fuyaient d'un clip à l'autre. Nouveau : les
  24 gabarits vidéo ouverts de ComfyUI qui prennent un clip en entrée (Bernini-R et
  Capybara *Video Edit*, inpainting VOID, upscale SeedVR2, remplacement de personnage
  SCAIL-2, Wan Animate 2, VACE…) sont listés comme moteurs à 0 $ dans les deux
  éditions, Seedance 2.5 nomme sa tâche (`editing`) et accepte 30 s, et l'interrupteur
  lip-sync nomme le moteur qu'il utilise réellement.
- **Les serveurs locaux démarrent tout seuls.** Quand un moteur a besoin de ComfyUI
  Desktop, du serveur MiniMax H3 local, d'Ollama, de LM Studio, de Jan ou de llama.cpp
  et qu'il est installé mais pas lancé, PANDORA le lance quand vous cliquez sur
  Générer, affiche les secondes qui passent pendant sa mise en route, puis continue. La
  fenêtre d'installation n'apparaît que si le module manque vraiment (ou si vous
  désactivez le démarrage automatique dans Paramètres → Modules externes). Le bandeau
  sous le moteur reçoit un bouton « Lancer maintenant » en un clic, et l'IA texte
  relance d'elle-même Ollama ou LM Studio quand un appel les trouve endormis.
- **Dix éditeurs vidéo cloud dans « Modifier un clip », dans les deux éditions.** Kling
  O3 Edit (Pro, Standard, 4K) et Kling O1 Edit comprennent les mêmes balises @Video1 /
  @Image1 que Seedance ; Wan 2.7 Edit, HappyHorse Video Edit, Bernini-R Edit (le même
  modèle que le gabarit ComfyUI local), FLUX.3 Edit Video, Gemini Omni Flash 1.1 Edit et
  Lucy Edit Pro prennent une simple description. Chacun est une ligne d'une table
  (endpoint, champs, prix à la seconde) vérifiée d'après sa page fal.ai ; le clip garde
  sa durée et le coût est journalisé à la seconde. L'upscaler gagne SeedVR2 sur votre
  propre GPU via ComfyUI, à 0 $, en gardant le nom du fichier source pour le Relink de
  DaVinci.
- **Chaque moteur fal.ai relu fiche par fiche (24/09/2026) — prix, champs, nouveaux
  paliers.** Veo 3.1 était journalisé à « 1,00 $ par clip » alors que fal facture à la
  seconde selon la résolution et l'audio (un clip par défaut coûtait 3,20 $) ; il
  envoie maintenant la résolution, 4/6/8 s et l'interrupteur audio, en paliers Pro,
  Fast et Lite, en texte et en image vers vidéo. Sora 2 était bloqué à 4 s : il accepte
  maintenant de 4 à 20 s à 0,10 $/s, plus Sora 2 Pro (720p → vrai 1080p) et l'image
  vers vidéo. Kling O3 Pro et Standard rejoignent le palier 4K (tous trois avec image
  de fin — l'appel image vers vidéo en 4K envoyait un mauvais nom de champ et aurait été
  refusé). PixVerse v6 reçoit l'image vers vidéo (la v4.5 a quitté fal), 1–15 s et le
  *bon* champ audio (`generate_audio_switch` — l'audio n'était silencieusement jamais
  produit), avec des prix par résolution. Nouveaux moteurs dans les deux éditions :
  Wan 3.0 (2–30 s en une seule prise, audio), LTX-2.3 Pro, Gemini Omni Flash 1.1 et
  Grok Imagine 1.5, en texte et en image vers vidéo. LTX-2 envoie désormais ses vraies
  durées (6/8/10 s) et résolutions (1080p → 2160p) ; Wan 2.7 envoie la résolution qu'il
  facture ; Seedance 2.5 propose le 1080p ajouté par fal (1,16 $/s, jamais par défaut).
  Prix de Kling v3 Pro, Kling v3 Turbo (champ de l'image de départ), PixVerse et Kling
  O3 corrigés dans « Coût du projet ». Les sélecteurs d'images de l'onglet Génération
  directe passaient des chemins locaux à fal : ils sont désormais téléversés. Le
  lip-sync gagne Kling Lipsync (~0,84 $/min, clips de 2 à 10 s) et PixVerse Lipsync
  (~2,40 $/min) ; l'upscaler gagne Topaz Astra 2 (génératif) et SeedVR2 respecte enfin
  le facteur ×2/×4. Images : Seedream 5.0 Flash, Qwen-Image 2 et 2 Pro, Kling Image O3
  (jusqu'à 10 références) et GPT Image 2.5 Flare rejoignent le catalogue ; FLUX.2 pro
  sait éditer avec des références ; le libellé de GPT Image 2 annonçait ~0,04 $ pour
  une image qui coûte environ 0,20 $ (facturée au token).
- **Version installée : les gabarits ComfyUI H3 sont de nouveau trouvés.** L'installeur
  livrait bien les trois fichiers de workflow MiniMax H3, mais l'application les
  cherchait dans son dossier de données au lieu de son dossier programme, si bien que
  chaque génération H3 sur ComfyUI s'arrêtait sur « Aucun workflow ComfyUI ». Les
  ressources embarquées se résolvent désormais depuis le dossier programme dans les
  deux éditions, avec un test qui simule la version compilée.

## 2.3.0 · 2026-08-30

**Un livre entier peut désormais être découpé — et on vous dit ce que cela coûtera
avant que vous ne dépensiez quoi que ce soit.**

Un utilisateur a collé un livre entier dans le Scénario. L'analyse est passée, et le
découpage s'est arrêté. Il ne pouvait pas réussir : un découpage fait environ six fois
la longueur de son texte d'entrée, et une passe unique plafonne vers 58 000 caractères.
Ce plafond est maintenant mesuré, annoncé et contourné.

- **Le découpage et le storyboard se font désormais par lots successifs.** Chaque lot
  est dimensionné pour tenir dans un seul appel, si bien que plus rien n'a besoin de la
  boucle de continuation qui relisait à chaque tour tout ce qui était déjà écrit. Si le
  septième lot échoue, les six premiers sont conservés et vous sont proposés — jamais
  jetés.
- **Un avertissement de taille avant toute dépense.** Au-delà d'une certaine longueur,
  PANDORA annonce le nombre de plans attendu, les passes nécessaires et un ordre de
  grandeur du coût, puis propose le mode par lots. Quand une passe unique ne peut
  vraiment pas aboutir, le bouton « Découper d'une traite quand même » n'est pas
  proposé du tout.
- **Perte silencieuse de plans au-delà de PLAN 999 corrigée.** Les numéros de plan
  étaient lus avec un motif à trois chiffres : au-delà de 999, les fiches étaient
  invisibles pour l'analyseur *et le contrat validait quand même*. Sur une œuvre
  longue, des centaines de plans pouvaient disparaître sans un seul message d'erreur.
- **Les appels IA texte sont enfin comptés dans « Coût du projet ».** La fenêtre avait
  une ligne « Texte (IA) » que rien n'alimentait jamais — analyse, découpage et
  storyboard affichaient tous 0,00 $. La consommation de tokens est maintenant lue dans
  la réponse et chiffrée.
- **Voix de doublage réparées.** Trois des sept moteurs étaient purement et simplement
  rejetés par fal (ils attendent `prompt`, PANDORA envoyait `text`), et les autres
  retombaient sur leur voix anglaise par défaut — c'est ce qui faisait sonner faux le
  français. Les quatre voix françaises natives d'Inworld (Alain, Hélène, Mathieu,
  Étienne) étaient dans l'application depuis le début, inatteignables, à un dixième du
  prix d'ElevenLabs.
- **Voice Changer.** Vous dites la réplique vous-même, en français, et le modèle ne
  change que le timbre — la prononciation ne peut donc pas être fausse.
- **Écouter une voix avant de la choisir.** fal ne publie aucun échantillon de voix,
  alors PANDORA génère une courte phrase en français par voix et la met en cache : la
  première écoute coûte une fraction de centime, chaque réécoute est gratuite.
- **Nouveaux moteurs de voix :** Qwen Audio 3.0 TTS, ByteDance Seed Speech v2 (avec des
  indications de jeu en langage courant), Async TTS Pro, xAI TTS.

## 2.2.0 · 2026-08-12

**Le prompt que vous lisez dans le Storyboard est désormais le prompt envoyé.**

Jusqu'ici, le Storyboard contenait un document de travail en français, et le *vrai*
prompt était écrit au dernier moment, à l'envoi, dans le Studio — invisible, et perdu à
la fermeture de l'application. Le pipeline tourne désormais dans le bon sens.

- **Les deux prompts naissent avec le storyboard et restent synchronisés.** Le
  découpage écrit le document de travail structuré *et* le prompt final prêt pour le
  moteur, et enregistre les deux avec le plan. Modifiez l'un et l'autre est
  reconstruit ; le Studio ne compose plus rien, il lit. Une bascule **Prompt structuré /
  Prompt final** dans la barre du Storyboard vous montre exactement lequel vous
  regardez.
- **Vous choisissez le moteur cible avant l'écriture du découpage.** Chaque moteur
  attend une forme de prompt différente, et l'adapter après coup sur des dizaines de
  plans oblige à tout recomposer. La fenêtre annonce les vraies contraintes du moteur
  choisi — résolutions, durées, manière d'adresser les fiches de référence.
- **Les storyboards existants peuvent rattraper leur retard.** Un bouton **Composer**
  remplit les prompts finaux des plans qui n'en ont jamais eu, avec un décompte pour
  connaître le coût avant de cliquer, et une fenêtre de progression pendant le travail.
- **Seedance 2.5** — prises uniques de 30 secondes, jusqu'à 50 références
  multimodales, et fiches adressées par leur nom dans le prompt (`@Image1`). Il est
  ajouté *à côté* de Seedance 2.0, jamais à sa place : il plafonne à 720p et coûte 56 %
  de plus à résolution égale, donc le 1080p et la 4K restent l'affaire de la 2.0.
- **Happy Horse 1.1** remplace la 1.0 — le 1080p passe à 0,18 $/s au lieu de 0,28 $/s.
- **Flux 3 (Black Forest Labs)** — texte vers vidéo, image vers vidéo et
  première-dernière image, de 5 à 20 secondes, audio natif. Son **palier brouillon**
  fait le rendu à 0,06 $/s : générez tout le film à petit prix, regardez-le, puis
  appuyez sur **✦ Affiner** dans la Vidéothèque pour ne rendre en 1080p complet que les
  prises que vous gardez. L'affinage réutilise le cache du brouillon, il rejoue donc
  exactement le même plan — ce n'est pas un nouveau tirage. À noter : Flux 3 n'a aucun
  mécanisme d'image de référence : les fiches de personnage et de décor ne peuvent pas
  être jointes, et PANDORA le dit plutôt que de les abandonner en silence.
- **Kling v3 Turbo** — un palier plus rapide et moins cher du moteur Kling déjà présent
  (0,14 $/s en pro, 0,112 $/s en standard).
- **VEED Lipsync v2** rejoint les moteurs de lip-sync (~4,20 $/min), entre Sync 2 Pro
  et Sync 2.
- **Stable Audio 3** pour la musique et les effets sonores, aux côtés de la 2.5. fal ne
  publie pas encore de grille tarifaire pour cette famille, et le sélecteur le dit au
  lieu d'afficher un chiffre inventé.
- **Le dossier des projets est désormais visible dans les Paramètres**, dans les deux
  éditions. Il n'était proposé que dans la fenêtre « Nouveau projet », si bien qu'après
  votre premier projet, plus moyen de le retrouver. Pratique pour travailler depuis un
  disque externe sur deux machines.
- **Grille tarifaire fal.ai corrigée.** Le 1080p était 12 % sous le vrai prix et le
  palier Fast 34 % en dessous ; Seedance Mini n'avait aucune entrée et retombait sur un
  chiffre quatre fois trop élevé. La fenêtre « Coût du projet » est de nouveau exacte.
- Corrigé : les lignes du tableau ne rognent plus un mouvement de caméra sur deux
  lignes ; un plantage en quittant le Storyboard pendant la composition des prompts ;
  et les plans dont le dialogue contient des points de suspension ou des apostrophes
  typographiques ne sont plus rejetés comme « altérés ».

## 2.1.1 · 2026-07-31

**Vos fiches de référence atteignent enfin le moteur — et l'application cesse de
ramer.**

- **Les images de référence sont désormais DÉCRITES au moteur, pas seulement
  envoyées.** Sur un plan avec un personnage et un décor, trois fiches étaient
  téléversées et *aucune* n'était annoncée : le rédacteur de prompt produisait une
  description autonome de la scène, et un endpoint d'édition d'image suit le texte
  plutôt que des images dont on ne lui a rien dit. Chaque image jointe est maintenant
  nommée avec son rôle et le nom de sa fiche (« la fiche personnage de “Jésus” — garde
  ce visage, ce costume **et le rendu dessiné de la fiche** »). La fenêtre Mood montre
  exactement quelles images partent, avec le plafond du moteur (`3/10`).
- **Toute la note de réalisation atteint le prompt.** Seule la première ligne
  correspondante du bloc de style visuel survivait : sur une note rédigée en puces,
  douze lignes sur treize étaient perdues et le moteur ne recevait jamais le style. Le
  repli prend maintenant tout le paragraphe — et un style figé tronqué dans un
  storyboard existant est réparé, tandis qu'un style réécrit à la main est laissé
  intact.
- **L'image du décor est un LIEU, pas le cadrage.** Un plan serré sur un personnage
  debout à gauche du cadre renvoyait encore la vue d'ensemble de la fiche du décor.
  Nouveau réglage **Image du décor** dans RENDU & AUDIO : *Lieu* (par défaut — la
  caméra s'y déplace en suivant l'axe et la valeur du plan), *Identique* (l'image EST
  le cadrage), *Inspiration*.
- **L'application est bien plus rapide.** Les cartes décodaient leur fichier source à
  chaque construction — une fiche personnage fait 2160×3840 pour une vignette de
  162 px — et la page Castings vidait même le cache au préalable. Les vignettes sont
  désormais mises en cache à la taille d'affichage : **Storyboard 6,6 s → 0,1 s,
  Décors 0,80 s → 0,03 s, clic sur une carte 116 → 24 ms**.
- **Le casting est séparé en Personnages principaux et Figuration**, deux sections
  repliables. Les castings existants se rangent d'eux-mêmes : une fiche dont le rôle
  indique déjà « Figurant » est classée en figuration.
- **Accessoires, HMC et Véhicules sont regroupés par catégorie**, Décors gagne une
  section « Vue d'ensemble des décors » et un bandeau repliable « Plan des décors ». Les
  grilles utilisent maintenant la **vraie largeur disponible** et se réorganisent quand
  le panneau latéral s'ouvre — fini les vignettes rognées.
- **Nouveau bouton « Coût du projet »**, à côté de Paramètres : chaque opération
  facturée avec son prix, et un total. Les montants sont clairement présentés comme des
  estimations.
- Le chat IA du storyboard **applique de nouveau les modifications en masse**
  (remplacer un bloc de style sur 75 plans dépassait la limite de réponse et
  n'appliquait rien, en silence), et affiche une **barre de progression** pendant sa
  réflexion.
- Atelier multi-angles : gauche et droite étaient inversées, « Avant » dupliquait votre
  image maîtresse et « Plafond » était hors de portée du moteur — l'atelier ne demande
  plus que les quatre vues qu'il sait réellement produire, et le dit.
- « Image & Son » retiré (inutilisé). Corrigé : une `IndexError` au démarrage, et un
  test de prix qui passait au rouge simplement parce que la machine utilisait un autre
  fournisseur.

## 2.1.0 · 2026-07-30

**Le mapping Live ne dérive plus — et chaque image arrive exactement à la taille
demandée.**

Cette version s'attaque à la plainte n° 1 sur le travail de mapping vidéo : au bout de
quelques plans, les clips générés zoomaient lentement, se rognaient et quittaient peu à
peu le bâtiment. La cause était structurelle — chaque plan repartait d'une image
extraite de la *vidéo* précédente, si bien que la petite dérive de chaque génération
était réinjectée et s'accumulait, comme la photocopie d'une photocopie.

- **Nouveau mode « Chaîne d'images » (par défaut) dans Séquence Mapping.** Les plans
  sont générés en image vers vidéo avec une image de départ et une image d'arrivée :
  chaque plan *se termine* sur son propre Mood et le plan suivant *démarre* de ce même
  fichier. Identité, pas extraction — l'effet boule de neige disparaît par
  construction. Le plan 1 reçoit deux vignettes (état de départ + état d'arrivée) ;
  tous les plans suivants s'enchaînent automatiquement. L'ancien mode à partir des
  frames est toujours là, derrière la bascule **Mode** à côté d'ACTION.
- **Vignettes de départ et d'arrivée directement dans le storyboard.** Cliquez sur
  l'une ou l'autre pour générer ou régénérer cet état seul, sans lancer tout le lot.
  Vous pouvez aussi **importer votre propre image** comme Mood — en Live *comme* en
  Cinéma.
- **Des images à la résolution exacte choisie.** Tous les ratios sauf le 1:1 étaient
  rendus en silence aux tailles des buckets SDXL (une demande en 16:9 revenait en
  1368×768). Toute la génération d'images livre désormais la définition exacte
  sélectionnée, 1920×1080 par défaut, et les moods du lot sont conformés au pixel près
  avant d'être enregistrés.
- **Masquage de façade réparé.** Le masque de confinement ne faisait silencieusement
  rien sur les façades RGBA, et le réappliquer mangeait un pixel à chaque passe.
  Corrigé, cache reconstruit, et l'option est désormais clairement activable
  (désactivée par défaut) dans RENDU & AUDIO.
- **Le prompt du Mood est composé par l'IA dans la grammaire du moteur** — générations
  par lot comme unitaires, dans les deux éditions, avec un cache persistant pour
  qu'une composition ne soit jamais payée deux fois. Les volets du prompt et de
  l'aperçu sont désormais repliables ; dépliez le prompt seul et il prend toute la
  hauteur.
- **Nouvelle organisation des dossiers de projet.** Les nouveaux projets sont créés
  avec une structure propre, numérotée et en anglais (`01_writing`, `02_elements`,
  `03_production`, `04_live`, `.cache` masqué). **Les projets existants ne sont pas
  touchés** — ils gardent leurs dossiers historiques pour toujours et tout continue de
  fonctionner : aucune migration, rien à faire.
- **Les écritures du fichier de configuration sont désormais atomiques** — un plantage
  en pleine sauvegarde ne peut plus corrompre vos clés API ; un fichier corrompu est
  mis en quarantaine et reconstruit au lieu de faire tomber l'application.
- **L'intégration Resolume est mise de côté pour l'instant** — l'onglet et les boutons
  sont retirés de l'édition Live ; les sets générés vivent dans le dossier vidéos du
  projet, prêts à être importés dans n'importe quel logiciel de VJ. Le moteur reste
  dans le code et pourrait revenir.
- Et aussi : « Générer les Moods » en lot respecte l'ancrage à deux plaques (un plan
  *part* de la frame précédente et *arrive* sur son Mood), les images de référence
  redeviennent de vraies inspirations, la génération de Mood peut être annulée, une
  surbrillance vert néon signale le Mood actif, les erreurs sont lisibles partout, et
  les deux manuels d'utilisation (Cinéma + Live) sont à jour en français et en anglais.

## 2.0.2 · 2026-07-26

**L'édition Live rattrape l'édition Cinéma — y compris un bug silencieux de perte de
données.**

- **Votre découpage Live est enfin réellement enregistré.** Il ne l'a jamais été : à
  partir du deuxième enregistrement, une clé canonique vide l'écrasait à chaque fois.
  PANDORA affichait « découpage appliqué ✓ » et ne gardait rien — à la réouverture,
  l'onglet était vide *et* grisé, et vos séquences retombaient en silence sur le
  conducteur brut au lieu de vos prompts co-écrits. **Tous ceux qui travaillent en Live
  devraient vérifier leurs découpages en cours.**
- **Le découpage Live utilise le contrat de fiches de plan « DÉCOUPAGE PANDORA 2 »**,
  comme l'édition Cinéma : source du conducteur, intention, rythme, durée, prompt
  visuel, personnages, accessoires, véhicules — plus `SON`, un champ propre au Live qui
  alimente le sound design et le calage musical. Les découpages existants au format
  plat continuent de fonctionner ; rien à migrer.
- **L'onglet Découpage est modifiable.** Il était en lecture seule dans le Live : une
  fois généré, impossible de supprimer un plan, de corriger une durée ou de réécrire un
  prompt. Les modifications s'enregistrent automatiquement.
- **Les séquences Live ne sont plus redécoupées par le moteur Cinéma**, qui appliquait
  le contrat du film, reconstruisait les prompts et abandonnait entièrement le sound
  design.
- **« Synchronisation » ne peut plus détruire vos prompts VJ.** Deux opérations
  héritées du Cinéma — réécrire les prompts et reconstruire un scénario — disparaissent
  de la fenêtre du Live.
- **Une durée écrite sous forme de timecode est lue correctement.** `0:20` était
  interprété comme **zéro seconde**, en silence, dans les deux éditions.
- **Plus de fenêtre d'erreur à la fermeture de PANDORA** (un worker testé après la
  destruction de son objet C++).
- Les erreurs d'IA texte nomment le bon fournisseur — un compte texte épuisé ne vous
  envoie plus recharger fal.ai. Plafond d'extraction relevé à 16 000 tokens. Colonne et
  réglage de profondeur de champ portés dans le Live. Le découpage est validé, relancé
  une fois, et refusé plutôt qu'enregistré cassé. L'analyse musicale et la note de
  réalisation atteignent désormais la co-écriture Live.

## 2.0.1 · 2026-07-26

Un correctif rapide pour un bug de perte de données découvert dans la 2.0.0, qui
mérite sa propre version.

- **Le découpage n'est plus jamais tronqué en silence.** Sur un scénario de long
  métrage, le moteur atteignait sa limite de sortie et s'arrêtait en plein document —
  au plan 28, environ la moitié du script. Comme le contrat valide chaque plan
  indépendamment, un demi-document dont tous les plans sont bien formés passait sans
  une seule erreur, et PANDORA enregistrait la moitié d'un film en croyant avoir fini.
  La coupure est désormais **détectée** et la suite demandée automatiquement (jusqu'à
  six tours), ou le découpage est **refusé avec un message explicite** — un découpage
  partiel est pire que pas de découpage du tout. Même correctif sur la mise en page
  Live.
- **Le bouton PayPal « Soutenir PANDORA » fonctionne.** Il pointait vers le point
  d'accès des dons de PayPal, réservé aux associations caritatives enregistrées, qui
  répondait toujours « this organization can't accept donations ». Il utilise
  désormais un lien PayPal.me.

Tous les utilisateurs de la 2.0.0 devraient mettre à jour.

## 2.0.0 · 2026-07-25

**Une version majeure — le prompt n'est plus un seul et même texte envoyé à tous les
moteurs.**

Jusqu'ici, le même prompt partait vers tous les moteurs vidéo et image, et chacun le
comprenait à sa façon. PANDORA **réécrit désormais votre plan dans le style d'écriture
du moteur qui va le recevoir** — et vous montre à l'écran, modifiable, le texte exact
qui sera envoyé. Ce seul changement touche toutes les générations de l'application,
d'où cette 2.0.

### Le prompt, reconstruit de bout en bout

- **Écrit dans la grammaire du moteur choisi.** Des lignes nommées `Camera / Lighting /
  Motion / Sound` pour Seedance, une seule phrase continue pour Veo et Sora, une
  directive d'action courte pour Kling, une prose dense pour les autres. Changer de
  moteur réassemble le prompt tout seul ; si vous avez modifié le texte à la main,
  votre version est adaptée, jamais écrasée.
- **Même règle pour les images**, partout dans l'application : un brief à champs nommés
  pour Nano Banana et GPT Image, une prose descriptive simple sans aucune négation pour
  Seedream (son API a abandonné les prompts négatifs — y écrire « no person » revient à
  demander une personne), un objet structuré pour FLUX.2.
- **Ce que vous voyez est ce qui est envoyé.** Sélectionnez un plan et l'encart se
  remplit de la prose anglaise finale, tout ce que PANDORA ajoute y étant écrit en
  clair. Modifiez-la mot à mot — rien n'est recollé ni retraduit ensuite, seul ou en
  lot.
- **Les fiches de votre projet atteignent vraiment le moteur.** L'apparence des
  personnages, les décors, accessoires, costumes et véhicules présents dans le plan
  sont désormais écrits dans le prompt. Fini le moteur qui invente un personnage qu'il
  ne connaissait que par son nom.
- **Le style visuel du film est transmis du scénario jusqu'au moteur** — capturé dans
  une section visible et modifiable sur chaque plan, traduit, et placé en fin de
  prompt, là où les moteurs le suivent le mieux. Les storyboards existants doivent être
  régénérés pour en profiter.
- **Chaque réglage caméra voyage.** Valeur de plan, axe, focale, profondeur de champ,
  distance, hauteur et vitesse s'arrêtaient au Storyboard. Ils sont désormais traduits
  et injectés, avec un *locked-off* explicite quand il n'y a pas de mouvement.
- **Rien de propre à la vidéo dans un prompt d'image** — mouvement de caméra, hauteur,
  vitesse, durée et son sont retirés (en français comme en anglais), et l'heure du plan
  devient une intention de lumière au lieu d'un mot brut.
- **Les interdits deviennent des descriptions positives** pour les moteurs qui ne
  savent pas exprimer une négation, et **les noms de studios ou de franchises sont
  retirés** de la charge utile, tandis que les descripteurs de style qui produisent
  réellement le rendu sont conservés.
- **Les dialogues sont écrits dans la langue du plan**, et **un prompt composé n'est
  jamais payé deux fois** — revenez sur un plan déjà préparé et il est réutilisé tel
  quel.

### Un moteur d'IA différent pour chaque tâche

Attribuez un modèle par usage : écriture du scénario, découpage, chat du storyboard,
prompt vidéo, traduction, direction artistique, analyse visuelle. Des profils par tâche
tout prêts pour Anthropic et ChatGPT, un bouton qui ne liste que les modèles que vos
clés débloquent vraiment, et la prise en charge d'un fournisseur personnalisé ou d'un
serveur local. **Quand quelque chose échoue, la vraie raison est affichée** — un solde
de crédits épuisé le dit désormais au lieu d'un vague « indisponible ».

### Scénario et découpage

- **Le découpage devient une série de fiches de plan** — l'extrait exact du scénario,
  l'intention, le rythme, la durée, le prompt visuel et les personnages présents,
  chaque plan pouvant être revu en co-écriture avant tout envoi. Les anciens découpages
  sont convertis automatiquement.
- **Un onglet Note de réalisation dédié** sépare les intentions de mise en scène (style
  visuel, lumière, rythme, grammaire de caméra, continuité, son) du texte narratif — et
  les transmet intactes au découpage.
- **La co-écriture est enregistrée et restaurée** à la réouverture du projet, et
  l'assistant du storyboard répond en entier tout en pilotant plus de colonnes.
- **Nouvelle colonne Profondeur de champ** dans le Storyboard, et toute la chaîne
  scénario → note de réalisation → découpage → storyboard est désormais présentée comme
  une chaîne.

### Images et éléments

- **Chaque élément reçoit une identité visuelle canonique** déduite de son image active
  et modifiable à la main — changez l'image active et PANDORA propose de mettre à jour
  les plans où cet élément apparaît. La continuité ne repose plus sur votre mémoire.
- **Quatorze moteurs d'image, sélectionnables partout** — dans les moods du Storyboard
  et du Live et dans les cinq fiches d'éléments, là où il y en avait deux ou six.
  Seedream 5 Pro rejoint le catalogue.
- **Fond blanc garanti** sur le casting, les accessoires, les costumes et les
  véhicules : ces fiches sont renvoyées comme références au moteur vidéo, où un décor
  parasite contaminerait le plan.
- **Outpaint d'une image vers votre ratio cible** sans rien rogner, **sept vues
  assorties pour chaque décor**, un **chat de direction artistique dans les fiches
  d'éléments**, la **comparaison en une seule commande** des moteurs et des variantes,
  des références en glisser-déposer, et un nouveau style d'image **Arri 65**.

### Interface

Un nouvel écran d'accueil et un mur de projets illustré, un clic droit sur la vignette
d'un projet pour le renommer, le dupliquer ou le supprimer, un seul menu **Action** sur
chaque page, le plan de feu transformé en véritable poste de travail synchronisé dans
les deux sens avec le storyboard, et la molette de la souris ne modifie plus un réglage
par accident.

### Fiabilité

Le français ne fuit plus dans les prompts (quatre fuites distinctes colmatées, dont un
traducteur qui répondait au lieu de traduire), vos modifications de prompt ne sont plus
perdues, la génération d'images ne se fige plus et ne plante plus, et les gros dossiers
comme les pages chargées d'images s'ouvrent instantanément.

### Live / mapping

L'édition Live suit l'édition Cinéma : même interface retravaillée, mêmes fiches de
plan, mêmes prompts de mood par moteur, mêmes correctifs.

> Version précédente (v1.3.5) : distributeur vidéo low cost, photos importées dans les
> fiches d'éléments, reproduction en fidélité exacte, premier lancement plus
> accueillant. Historique complet : [Releases](https://github.com/22eme-Arkane/PANDORA/releases).
