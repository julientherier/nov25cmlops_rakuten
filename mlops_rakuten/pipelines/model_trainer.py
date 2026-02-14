from pathlib import Path

from loguru import logger

from mlops_rakuten.config.config_manager import ConfigurationManager
from mlops_rakuten.modules.model_trainer import ModelTrainer


class ModelTrainerPipeline:
    """
    Pipeline d'entraînement du modèle :
    - charge la configuration
    - exécute l'étape ModelTrainer
    - renvoie le chemin du modèle entraîné
    """

    def run(self) -> Path:
        logger.info("Démarrage du pipeline ModelTrainer")

        config_manager = ConfigurationManager()
        model_trainer_config = config_manager.get_model_trainer_config()

        step = ModelTrainer(config=model_trainer_config)
        model_path = step.run()

        logger.success(f"Pipeline ModelTrainer terminé. Modèle créé : {model_path}")
        return model_path
    
if __name__ == "__main__":
    pipeline = ModelTrainerPipeline()
    pipeline.run()
