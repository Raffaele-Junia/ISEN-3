import cv2
import mediapipe as mp
import random
import urllib.request
import os
import time

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")

if not os.path.exists(MODEL_PATH):
    print("Téléchargement du modèle...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Modèle téléchargé.")

base_options = mp.tasks.BaseOptions(
    model_asset_path=MODEL_PATH
)

options = mp.tasks.vision.HandLandmarkerOptions(
    base_options=base_options,
    num_hands=1,
    min_hand_detection_confidence=0.6,
    min_hand_presence_confidence=0.6,
    min_tracking_confidence=0.6
)

landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)

cap = cv2.VideoCapture(0)

choix = ["Pierre", "Papier", "Ciseaux"]

score_joueur = 0
score_ordi = 0

choix_ordi = random.choice(choix)

message = "Montre ta main"
dernier_choix = "Aucun"

bloque = False
temps_resultat = 0

def compter_doigts(landmarks):
    doigts = 0

    if landmarks[8].y < landmarks[6].y:
        doigts += 1

    if landmarks[12].y < landmarks[10].y:
        doigts += 1

    if landmarks[16].y < landmarks[14].y:
        doigts += 1

    if landmarks[20].y < landmarks[18].y:
        doigts += 1

    if landmarks[4].x < landmarks[3].x:
        doigts += 1

    return doigts


def reconnaitre_geste(nombre_doigts):
    if nombre_doigts == 0:
        return "Pierre"

    if nombre_doigts == 2:
        return "Ciseaux"

    if nombre_doigts == 5:
        return "Papier"

    return "Inconnu"


def resultat(joueur, ordinateur):
    if joueur == ordinateur:
        return "Egalite"

    if (
        joueur == "Pierre" and ordinateur == "Ciseaux"
        or joueur == "Papier" and ordinateur == "Pierre"
        or joueur == "Ciseaux" and ordinateur == "Papier"
    ):
        return "Joueur"

    return "Ordinateur"


while True:
    ret, frame = cap.read()

    if not ret:
        break

    frame = cv2.flip(frame, 1)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=rgb
    )

    detection = landmarker.detect(image)

    choix_joueur = "Aucun"

    if detection.hand_landmarks:
        landmarks = detection.hand_landmarks[0]

        nombre_doigts = compter_doigts(landmarks)
        choix_joueur = reconnaitre_geste(nombre_doigts)

        h, w, _ = frame.shape

        for point in landmarks:
            x = int(point.x * w)
            y = int(point.y * h)

            cv2.circle(
                frame,
                (x, y),
                5,
                (0, 255, 0),
                -1
            )

    if choix_joueur in choix and not bloque:
        dernier_choix = choix_joueur

        gagnant = resultat(choix_joueur, choix_ordi)

        if gagnant == "Joueur":
            score_joueur += 1
            message = "Tu gagnes la manche !"

        elif gagnant == "Ordinateur":
            score_ordi += 1
            message = "L'ordinateur gagne la manche !"

        else:
            message = "Egalite !"

        bloque = True
        temps_resultat = time.time()

    if bloque:
        temps_ecoule = time.time() - temps_resultat
        temps_restant = max(0, 2 - int(temps_ecoule))

        cv2.putText(
            frame,
            f"Prochaine manche dans : {temps_restant}",
            (30, 250),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        if temps_ecoule >= 5:
            if score_joueur < 3 and score_ordi < 3:
                choix_ordi = random.choice(choix)
                message = "Montre ta main"
                dernier_choix = "Aucun"
                bloque = False

    if score_joueur >= 3:
        message = "TU GAGNES LE MATCH !"

    elif score_ordi >= 3:
        message = "L'ORDINATEUR GAGNE LE MATCH !"

    cv2.putText(
        frame,
        f"Toi : {dernier_choix}",
        (30, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        2
    )

    cv2.putText(
        frame,
        f"Ordinateur : {choix_ordi}",
        (30, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 0, 0),
        2
    )

    cv2.putText(
        frame,
        f"Score : {score_joueur} - {score_ordi}",
        (30, 150),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2
    )

    cv2.putText(
        frame,
        message,
        (30, 200),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2
    )

    if score_joueur >= 3 or score_ordi >= 3:
        cv2.putText(
            frame,
            "Appuie sur R pour recommencer",
            (30, 300),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

    cv2.imshow("Pierre Papier Ciseaux", frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

    if key == ord("r") and (score_joueur >= 3 or score_ordi >= 3):
        score_joueur = 0
        score_ordi = 0
        choix_ordi = random.choice(choix)
        dernier_choix = "Aucun"
        message = "Montre ta main"
        bloque = False

cap.release()
landmarker.close()
cv2.destroyAllWindows()