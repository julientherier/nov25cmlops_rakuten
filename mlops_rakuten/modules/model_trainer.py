import json
from pathlib import Path
import pickle

from loguru import logger
import numpy as np
from scipy import sparse
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.svm import LinearSVC

from mlops_rakuten.config.entities import ModelTrainerConfig
from mlops_rakuten.utils import create_directories


class ModelTrainer:
    """
    Étape d'entraînement du modèle Rakuten.

    - Charge X_train et y_train transformés (TF-IDF + label encoding)
    - Instancie le modèle sklearn (par défaut LinearSVC)
    - Entraîne le modèle
    - Calcule quelques métriques sur le jeu d'entraînement
    - Sauvegarde :
        - le modèle entraîné (text_classifier.pkl)
        - un fichier JSON décrivant la configuration d'entraînement
        - un fichier JSON contenant les métriques d'entraînement
        - un rapport texte de classification sur le train
    """

    def __init__(self, config: ModelTrainerConfig) -> None:
        self.config = config

    def _build_model(self):
        """
        Construit le modèle sklearn en fonction de la configuration.
        """
        cfg = self.config

        if cfg.model_type == "linear_svc":
            class_weight = "balanced" if cfg.use_class_weight else None
            logger.info(
                f"Instanciation d'un LinearSVC (C={cfg.C}, "
                f"max_iter={cfg.max_iter}, class_weight={class_weight})"
            )
            return LinearSVC(
                C=cfg.C,
                max_iter=cfg.max_iter,
                class_weight=class_weight,
            )

        if cfg.model_type == "logistic_regression":
            class_weight = "balanced" if cfg.use_class_weight else None
            logger.info(
                "Instanciation d'une LogisticRegression "
                f"(C={cfg.C}, max_iter={cfg.max_iter}, "
                f"class_weight={class_weight}, multi_class='multinomial')"
            )
            return LogisticRegression(
                C=cfg.C,
                max_iter=cfg.max_iter,
                class_weight=class_weight,
            )

        raise ValueError(
            f"Type de modèle non supporté : '{cfg.model_type}'. "
            "Actuellement 'linear_svc' et 'logistic_regression' sont gérés."
        )

    def run(self) -> Path:
        """
        Entraîne le modèle et retourne le chemin du fichier modèle sauvegardé.
        """
        logger.info("Démarrage de l'étape ModelTrainer")

        cfg = self.config

        # 1. Charger les données d'entraînement
        logger.info(f"Chargement de X_train depuis : {cfg.X_train_path}")
        X_train = sparse.load_npz(cfg.X_train_path)

        logger.info(f"Chargement de y_train depuis : {cfg.y_train_path}")
        y_train = np.load(cfg.y_train_path)

        logger.debug(f"X_train shape: {X_train.shape}")
        logger.debug(f"y_train shape: {y_train.shape}")

        # 2. Construire le modèle
        model = self._build_model()

        # 3. Entraîner le modèle
        logger.info("Entraînement du modèle")
        model.fit(X_train, y_train)
        logger.success("Modèle entraîné avec succès")

        # 4. Évaluer sur le jeu d'entraînement (baseline)
        logger.info("Évaluation du modèle sur le jeu d'entraînement")
        y_pred_train = model.predict(X_train)

        train_accuracy = accuracy_score(y_train, y_pred_train)
        train_f1_macro = f1_score(y_train, y_pred_train, average="macro")

        logger.info(f"Train accuracy: {train_accuracy:.4f}")
        logger.info(f"Train F1 macro: {train_f1_macro:.4f}")

        # Rapport de classification détaillé
        cls_report = classification_report(y_train, y_pred_train)

        # 5. Créer le répertoire des modèles si besoin
        create_directories([cfg.model_dir])

        # 6. Sauvegarder le modèle
        logger.info(f"Sauvegarde du modèle vers : {cfg.model_path}")
        with open(cfg.model_path, "wb") as f:
            pickle.dump(model, f)

        # 7. Sauvegarder un fichier de configuration lisible
        model_config_path = cfg.model_dir / "model_config.json"
        logger.info(f"Sauvegarde de la configuration du modèle vers : {model_config_path}")

        model_config = {
            "model_type": cfg.model_type,
            "params": {
                "C": cfg.C,
                "max_iter": cfg.max_iter,
                "use_class_weight": cfg.use_class_weight,
            },
            "training_data": {
                "X_train_path": str(cfg.X_train_path),
                "y_train_path": str(cfg.y_train_path),
            },
        }

        with open(model_config_path, "w") as f:
            json.dump(model_config, f, indent=2)

        # 8. Sauvegarder les métriques d'entraînement
        metrics_path = cfg.model_dir / "metrics_train.json"
        logger.info(f"Sauvegarde des métriques d'entraînement vers : {metrics_path}")

        metrics = {
            "train_accuracy": train_accuracy,
            "train_f1_macro": train_f1_macro,
        }

        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)

        # 9. Sauvegarder le rapport de classification texte
        cls_report_path = cfg.model_dir / "classification_report_train.txt"
        logger.info(f"Sauvegarde du rapport de classification (train) vers : {cls_report_path}")

        with open(cls_report_path, "w") as f:
            f.write(cls_report)

        logger.success("ModelTrainer terminé avec succès")
        return cfg.model_path
