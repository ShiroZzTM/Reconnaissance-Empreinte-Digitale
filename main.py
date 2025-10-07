import os
import cv2
import numpy as np

# Trouve les dossiers de dataset (sous-répertoires contenant des images)
def find_datasets():
    dirs = [d for d in os.listdir('.') if os.path.isdir(d)]
    datasets = []
    for d in sorted(dirs):
        files = [f for f in os.listdir(d)
                 if os.path.isfile(os.path.join(d, f))
                 and f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'))]
        if len(files) >= 1:
            datasets.append(d)
    return datasets

# Laisse l'utilisateur sélectionner un dossier parmi les datasets trouvés
def choose_dataset():
    datasets = find_datasets()
    if not datasets:
        print("Aucun dataset trouvé dans le répertoire courant.")
        return None
    print("\nDatasets disponibles :")
    for idx, ds in enumerate(datasets, 1):
        print(f"{idx}. {ds}")
    while True:
        try:
            sel = int(input(f"Sélectionnez un dataset [1-{len(datasets)}] : ")) - 1
        except ValueError:
            print("Entrez un nombre valide.")
            continue
        if 0 <= sel < len(datasets):
            return datasets[sel]
        print("Index hors limites.")

# Liste les fichiers image d'un dossier donné
def list_images(dataset_dir):
    files = [f for f in sorted(os.listdir(dataset_dir))
             if os.path.isfile(os.path.join(dataset_dir, f))
             and f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'))]
    for idx, fname in enumerate(files, 1):
        print(f"{idx}. {fname}")
    return files

# Prétraitement
# charge, passe en gris, lisse, puis binarise l’image pour mettre en évidence les crêtes
def preprocess_image(path):
    # Charge l’image depuis le chemin donné (BGR color)
    img = cv2.imread(path)
    # Si l’image n’a pas pu être chargée (chemin invalide, problème de fichier…)
    if img is None:
        # On lève une erreur explicite pour interrompre le programme
        raise FileNotFoundError(f"Impossible de charger l'image : {path}")
    # Convertit l’image couleur en niveaux de gris
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Applique un flou gaussien 5×5 pour réduire le bruit
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    # 1) L’image d’entrée (après flou), en niveaux de gris
    # 2) La valeur “maximale” : lorsqu’un pixel dépasse son seuil, on lui donne cette valeur (ici 255, blanc)
    # 3) La méthode qui calcule le seuil local :
    #    • GAUSSIAN_C = on fait une moyenne pondérée gaussienne des voisins
    #    • (autre option : MEAN_C, qui fait une moyenne simple)
    # 4) Le type de seuillage :
    #    • BINARY = pixels > seuil → blanc ; < seuil → noir
    #    • BINARY_INV = l’inverse : > seuil → noir ; < seuil → blanc
    # 5) La taille du voisinage carré autour de chaque pixel (ici 11×11)
    #    On calcule un seuil différent pour chaque pixel en regardant ses 5 pixels de chaque côté
    # 6) Une constante soustraite de la moyenne locale
    #    Si la moyenne gaussienne vaut M, le seuil = M − C
    # Plus strict et éviter que de très petits détails (bruit) soient considérés comme des crêtes
    return cv2.adaptiveThreshold(blur, 255,
                                 cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                 cv2.THRESH_BINARY_INV,
                                 blockSize=11, C=2)

# Extraction ORB
# utilise ORB pour repérer jusqu’à 500 points caractéristiques et produire leurs pointeurs, prêts pour le matching
def extract_features(img):
    # Initialise un détecteur ORB (500 points max)
    orb = cv2.ORB_create(nfeatures=500)
    return orb.detectAndCompute(img, None)


# Matching
def match_descriptors(desc1, desc2, ratio=0.75):

    # 1) Initialisation du matcher « brute-force » avec distance de Hamming
    #    - NORM_HAMMING : adapté aux descripteurs binaires (ORB, BRIEF…)
    #    - crossCheck=False : on ne force pas à n’autoriser que les matches mutuels
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

    # 2) Pour chaque descripteur de desc1, récupère les deux plus proches voisins dans desc2
    #    - k=2 : on veut les 2 meilleurs matches pour appliquer le ratio test ensuite
    matches = bf.knnMatch(desc1, desc2, k=2)

    good_matches = []
    for m, n in matches:
        if m.distance < ratio * n.distance:  # permet d’éliminer les correspondances ambiguës.
            good_matches.append(m)

    # 4) On renvoie la liste filtrée des correspondances fiables
    return good_matches


# Compare deux empreintes et optionnellement afficher
def compare_fingerprints(path1, path2, show=True):
    img1 = preprocess_image(path1)                      # Charge et prétraite la 1ʳᵉ empreinte
    img2 = preprocess_image(path2)                      # Charge et prétraite la 2ᵉ empreinte
    kp1, desc1 = extract_features(img1)                  # Extrait keypoints + descripteurs de img1
    kp2, desc2 = extract_features(img2)                  # Extrait keypoints + descripteurs de img2
    if desc1 is None or desc2 is None or not kp1 or not kp2:
        print("Extraction des points-clés a échoué.")    # Stop si pas de points valides
        return 0.0                                       # Renvoie 0% en cas d’échec
    matches = match_descriptors(desc1, desc2)            # Calcule les correspondances fiables
    score = len(matches)                                 # Nombre total de matches
    pct = (score / len(kp1)) * 100                       # Pourcentage de similarité
    print(f"Points image1: {len(kp1)}")                  # Affiche nb. keypoints de img1
    print(f"Points image2: {len(kp2)}")                  # Affiche nb. keypoints de img2
    print(f"Correspondances: {score}, Similarité: {pct:.2f}%")  # Résumé des résultats
    if show:
        o1 = cv2.imread(path1)                           # Recharge img1 en couleur pour l’affichage
        o2 = cv2.imread(path2)                           # Recharge img2 en couleur
        vis = cv2.drawMatches(
            o1, kp1, o2, kp2, matches, None,
            flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS
        )                                                # Dessine les lignes de correspondance
        cv2.namedWindow('Matches', cv2.WINDOW_NORMAL)    # Rend la fenêtre redimensionnable
        h, w = vis.shape[:2]                             # Récupère dimensions de l’image visuelle
        max_w, max_h = 1000, 800                         # Taille max avant redimensionnement
        scale = min(max_w / w, max_h / h, 1.0)           # Calcule le facteur d’échelle
        if scale < 1.0:
            vis = cv2.resize(vis, (int(w * scale), int(h * scale)))  # Redimensionne si nécessaire
        cv2.imshow('Matches', vis)                       # Affiche la fenêtre « Matches »
        while cv2.getWindowProperty('Matches', cv2.WND_PROP_VISIBLE) >= 1:
            cv2.waitKey(100)
        cv2.destroyAllWindows()
    return pct

# Trouver meilleure correspondance pour un index
def find_best_match(base_idx, files, dataset_dir):
    base = files[base_idx]                         # Récupère le nom du fichier de référence via son indic
    base_path = os.path.join(dataset_dir, base)   # Initialise la meilleure correspondance et son score
    best, best_pct = None, -1.0
    for i,fname in enumerate(files):             # Parcourt toutes les images du dataset
        # Ignore la comparaison de l’image avec elle-même
        if i==base_idx: continue
        # Compare l’image de référence avec chaque autre image
        pct = compare_fingerprints(base_path, os.path.join(dataset_dir, fname), show=False)
        if pct>best_pct:
            best_pct, best = pct, fname
    if best:
        print(f"\nMeilleure correspondance pour '{base}' → '{best}' ({best_pct:.2f}%)")
    else:
        print("Aucune autre image à comparer.")

# Menu principal
def main():
    while True:
        print("\n//////////////////// MENU ////////////////////")
        print("1. Comparer 2 empreintes")
        print("2. Trouver la meilleure correspondance")
        print("3. Quitter")
        c = input("Choix [1-3]: ")
        if c=='1' or c=='2':
            ds = choose_dataset()
            if not ds: continue
            files = list_images(ds)
            if len(files)<2:
                print("Pas assez d'images.")
                continue
        if c=='1':
            try:
                i1 = int(input("Choix de la 1ère image : "))-1
                i2 = int(input("Choix de la 2ème image : "))-1
            except ValueError:
                print("Entrées invalides.")
                continue
            if i1<0 or i2<0 or i1>=len(files) or i2>=len(files) or i1==i2:
                print("Indices invalides.")
                continue
            print(f"Comparaison: {files[i1]} vs {files[i2]}")
            compare_fingerprints(os.path.join(ds,files[i1]), os.path.join(ds,files[i2]))
        elif c=='2':
            try:
                idx = int(input("Choix de l'image de référence : "))-1
            except ValueError:
                continue
            if idx<0 or idx>=len(files):
                print("Indice hors limites.")
                continue
            find_best_match(idx, files, ds)
        elif c=='3':
            print("Au revoir !")
            break
        else:
            print("Choix inconnu.")

if __name__=='__main__':
    main()
