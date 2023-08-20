import fire

from pathlib import Path

from training_pipeline import configs


def infer(
    config_file: str,
    output_dir: str,
    dataset_dir: str,
    env_file_path: str = ".env",
    logging_config_path: str = "logging.yaml",
    model_cache_dir: str = None,
):
    import logging

    from training_pipeline import initialize

    # Be sure to initialize the environment variables before importing any other modules.
    initialize(logging_config_path=logging_config_path, env_file_path=env_file_path)

    from training_pipeline import utils
    from training_pipeline.api import FinQAInferenceAPI

    logger = logging.getLogger(__name__)

    logger.info("#" * 100)
    utils.log_available_gpu_memory()
    utils.log_available_ram()
    logger.info("#" * 100)

    config_file = Path(config_file)
    output_dir = Path(output_dir)
    root_dataset_dir = Path(dataset_dir)
    model_cache_dir = Path(model_cache_dir) if model_cache_dir else None

    inference_config = configs.InferenceConfig.from_yaml(config_file)
    inference_api = FinQAInferenceAPI.from_config(
        config=inference_config, root_dataset_dir=root_dataset_dir, model_cache_dir=model_cache_dir
    )
    inference_api.infer_all()


if __name__ == "__main__":
    fire.Fire(infer)
