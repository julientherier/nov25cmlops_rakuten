from typing import List, Any, Dict, Optional

from loguru import logger

from mlops_rakuten.config.config_manager import ConfigurationManager
from mlops_rakuten.modules.prediction import Prediction


class PredictionPipeline:
    """
    Pipeline d'inférence :
    - charge la configuration
    - instancie Prediction
    - expose une méthode `run(texts)` qui renvoie les prédictions
    """

    def __init__(self) -> None:
        config_manager = ConfigurationManager()
        inference_config = config_manager.get_prediction_config()
        self.infer = Prediction(config=inference_config)

    def run(self, texts: List[str], top_k: int | None = None):
        logger.info("Démarrage du pipeline d'inférence")
        preds = self.infer.predict(texts, top_k=top_k)
        logger.success("Inférence terminée")
        return preds

    def get_model_info(self) -> Optional[Dict[str, Any]]:
        return self.infer.get_model_info()