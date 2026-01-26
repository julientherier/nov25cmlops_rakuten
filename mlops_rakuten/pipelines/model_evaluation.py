from pathlib import Path

from loguru import logger

from mlops_rakuten.config.config_manager import ConfigurationManager
from mlops_rakuten.modules.model_evaluation import ModelEvaluation


class ModelEvaluationPipeline:
    """
    Pipeline d'évaluation du modèle :
    - charge la configuration
    - exécute l'étape ModelEvaluation
    - renvoie le chemin du fichier de métriques de validation
    """

    def run(self) -> Path:
        logger.info("Démarrage du pipeline ModelEvaluation")

        config_manager = ConfigurationManager()
        model_eval_config = config_manager.get_model_evaluation_config()

        step = ModelEvaluation(config=model_eval_config)
        metrics_path = step.run()

        logger.success(
            f"Pipeline ModelEvaluation terminé. "
            f"Métriques de validation disponibles dans : {metrics_path}"
        )
        return metrics_path

if __name__ == "__main__":  
    pipeline = ModelEvaluationPipeline()
    pipeline.run()