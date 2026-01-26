import pickle
import os

from loguru import logger
import numpy as np
import pandas as pd
import mlflow

from mlops_rakuten.config.entities import PredictionConfig
from mlops_rakuten.utils import check_required_data_files


class Prediction:
    """
    Étape d'inférence pour le modèle Rakuten. Utilise le registre de modèles MLflow et le modèle en statut "production".

    - Recharge le vectorizer TF-IDF
    - Recharge le LabelEncoder
    - Recharge le modèle entraîné
    - Expose une méthode `predict` qui prend une liste de textes
      et renvoie les prdtypecode d'origine.
    """

    MODEL_REGISTRY_NAME = "rakuten_text_classifier_tfidf"

    def __init__(self, config: PredictionConfig) -> None:
        self.config = config
        self._setup_mlflow()
        self._check_data_availability()
        self._load_artifacts()

    def _setup_mlflow(self):
        """Configure la connexion à DagsHub MLflow"""
        dagshub_token = os.getenv("DAGSHUB_TOKEN")
        dagshub_user = os.getenv("DAGSHUB_USER")
        dagshub_repo = os.getenv("DAGSHUB_REPO")

        if not all([dagshub_token, dagshub_user, dagshub_repo]):
            logger.warning("Variables d'env MLflow manquantes")
            self.mlflow_enabled = False
            return

        self.mlflow_enabled = True
        mlflow.set_tracking_uri(
            f"https://dagshub.com/{dagshub_user}/{dagshub_repo}.mlflow"
        )

        os.environ["MLFLOW_TRACKING_USERNAME"] = dagshub_user
        os.environ["MLFLOW_TRACKING_PASSWORD"] = dagshub_token

        logger.info("MLflow configuré")


    def _check_data_availability(self) -> None:
        """Vérifie que les fichiers de données d'entrée sont disponibles."""

        required_files = {
            "Fichier de correspondance de labels": self.config.categories_path,
        }

        logger.info("Vérification de la disponibilité des fichiers requis...")
        all_ok = check_required_data_files(required_files)

        if not all_ok:
            raise FileNotFoundError(
                "Le fichier de correspondance requis est invalide ou indisponible. "
                "Veuillez suivre les instructions du README pour les obtenir."
            )
        logger.info("✓ Fichiers disponibles")

    def _load_artifacts(self) -> None:
        """
        Charge les artifacts:
        - Vectorizer: local
        - LabelEncoder: local
        - Modèle: MLflow (alias "production")
        """
        cfg = self.config

        # Charger vectorizer (local)
        logger.info(f"Chargement du vectorizer depuis : {cfg.vectorizer_path}")
        with open(cfg.vectorizer_path, "rb") as f:
            self.vectorizer = pickle.load(f)
        logger.success("Vectorizer chargé")

        # Charger label encoder (local)
        logger.info(f"Chargement du LabelEncoder depuis : {cfg.label_encoder_path}")
        with open(cfg.label_encoder_path, "rb") as f:
            self.label_encoder = pickle.load(f)
        logger.success("LabelEncoder chargé")

        # Charger modèle depuis MLflow (alias "production")
        self._load_model_from_mlflow()

        # Charger le mapping prdtypecode -> category_name
        self.category_mapping: dict[int, str] | None = None
        if cfg.categories_path is not None:
            logger.info(f"Chargement des catégories depuis : {cfg.categories_path}")
            df_cat = pd.read_csv(cfg.categories_path)

            if cfg.category_code_column not in df_cat.columns:
                raise KeyError(
                    f"Colonne code '{cfg.category_code_column}' absente de {cfg.categories_path}"
                )
            if cfg.category_name_column not in df_cat.columns:
                raise KeyError(
                    f"Colonne nom '{cfg.category_name_column}' absente de {cfg.categories_path}"
                )

            self.category_mapping = dict(
                zip(
                    df_cat[cfg.category_code_column],
                    df_cat[cfg.category_name_column],
                )
            )
            logger.info(
                f"Mapping catégories chargé ({len(self.category_mapping)} entrées)"
            )

        logger.success("✓ Initialisation de Prediction terminée")

    def _load_model_from_mlflow(self) -> None:
        """
        Charge le modèle depuis MLflow avec l'alias "production"
        Si MLflow indisponible, charge depuis le fichier local
        """
        cfg = self.config

        # Essayer de charger depuis MLflow
        if self.mlflow_enabled:
            try:
                model_uri = f"models:/{self.MODEL_REGISTRY_NAME}@production"
                logger.info(f"Chargement du modèle depuis MLflow: {model_uri}")

                self.model = mlflow.sklearn.load_model(model_uri)
                logger.success(f"Modèle chargé depuis MLflow (alias 'production')")
                return

            except Exception as e:
                logger.warning(f"Impossible de charger depuis MLflow: {e}")
                logger.warning("  → Fallback vers fichier local")

        # Charger depuis fichier local
        logger.info(f"Chargement du modèle depuis fichier local: {cfg.model_path}")
        try:
            with open(cfg.model_path, "rb") as f:
                self.model = pickle.load(f)
            logger.success(f"Modèle chargé depuis {cfg.model_path}")
        except Exception as e:
            logger.error(f"Impossible de charger le modèle: {e}")
            raise

    def predict(self, texts, top_k: int | None = None):
        """
        Prend une liste de textes (designations produits)
        et renvoie un tableau de prdtypecode (int) prédits.

        Retourne, pour chaque texte, une liste de dicts:
        [
          {"prdtypecode": 10, "category_name": "Vêtements", "proba": 0.72},
          {"prdtypecode": 20, "category_name": "Smartphones", "proba": 0.18},
          ...
        ]

        Si top_k est défini, on ne garde que les top_k catégories par texte.
        """
        if isinstance(texts, str):
            texts = [texts]

        logger.info(f"Inférence (avec probabilités) sur {len(texts)} texte(s)")

        # 1. Vectorisation
        X_vec = self.vectorizer.transform(texts)

        # 2. Probabilités par classe (shape: n_samples x n_classes)
        if not hasattr(self.model, "predict_proba"):
            raise AttributeError(
                "Le modèle courant ne supporte pas predict_proba. "
                "Utilise 'logistic_regression' dans model_trainer.model_type."
            )

        proba = self.model.predict_proba(X_vec)  # np.ndarray

        # 3. Mapping des indices de classes -> prdtypecode d'origine
        #    Le LabelEncoder a un attribut `classes_` qui contient les codes
        prdtypecodes = self.label_encoder.inverse_transform(
            np.arange(len(self.label_encoder.classes_))
        )

        results_all_texts = []

        for i in range(proba.shape[0]):
            proba_i = proba[i]  # proba pour le texte i
            # indices triés par proba décroissante
            sorted_idx = np.argsort(proba_i)[::-1]

            if top_k is not None:
                sorted_idx = sorted_idx[:top_k]

            results_one_text = []
            for idx in sorted_idx:
                code = int(prdtypecodes[idx])
                p = float(proba_i[idx])

                if self.category_mapping is not None:
                    name = self.category_mapping.get(code)
                else:
                    name = None

                results_one_text.append(
                    {
                        "prdtypecode": code,
                        "category_name": name,
                        "proba": p,  # ex: 0.72
                    }
                )

            results_all_texts.append(results_one_text)

        return results_all_texts