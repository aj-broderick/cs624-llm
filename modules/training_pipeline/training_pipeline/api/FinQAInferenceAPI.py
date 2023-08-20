import logging
from pathlib import Path
from typing import Optional, Tuple

from datasets import Dataset
from training_pipeline.data import finqa
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftConfig

from training_pipeline.configs import InferenceConfig
from training_pipeline import constants, models


logger = logging.getLogger(__name__)


class FinQAInferenceAPI:
    def __init__(
        self,
        peft_model_id: str,
        model_id: str,
        root_dataset_dir: Optional[Path] = None,
        max_new_tokens: int = 50,
        model_cache_dir: Optional[Path] = None,
        device: str = "cuda:0",
    ):
        self._peft_model_id = peft_model_id
        self._model_id = model_id
        self._max_new_tokens = max_new_tokens
        self._root_dataset_dir = root_dataset_dir
        self._model_cache_dir = model_cache_dir
        self._device = device

        self._model, self._tokenizer, self._peft_config = self.load_model()
        if self._root_dataset_dir is not None:
            self._dataset = self.load_data()
        else:
            self._dataset = None

    @classmethod
    def from_config(
        cls,
        config: InferenceConfig,
        root_dataset_dir: Optional[Path] = None,
        model_cache_dir: Optional[Path] = None,
    ):
        return cls(
            peft_model_id=config.peft_model["id"],
            model_id=config.model["id"],
            root_dataset_dir=root_dataset_dir,
            max_new_tokens=config.model["max_new_tokens"],
            model_cache_dir=model_cache_dir,
            device=config.setup.get("device", "cuda:0"),
        )

    def load_data(self) -> Dataset:
        logger.info(f"Loading FinQA datasets from {self._root_dataset_dir=}")

        dataset = finqa.FinQADataset(
            data_path=self._root_dataset_dir / "private_test.json",
            scope=constants.Scope.INFERENCE,
            max_samples=20
        ).to_huggingface()

        logger.info(f"Loaded {len(dataset)} samples for inference")

        return dataset

    def load_model(self) -> Tuple[AutoModelForCausalLM, AutoTokenizer, PeftConfig]:
        logger.info(f"Loading model using {self._model_id=} and {self._peft_model_id=}")

        model, tokenizer, peft_config = models.build_qlora_model(
            pretrained_model_name_or_path=self._model_id,
            peft_pretrained_model_name_or_path=self._peft_model_id,
            gradient_checkpointing=False,
            cache_dir=self._model_cache_dir,
        )

        return model, tokenizer, peft_config

    def infer(self, question: str) -> str:
        answer = models.prompt(
            model=self._model,
            tokenizer=self._tokenizer,
            input_text=question,
            device=self._device,
        )

        return answer

    def infer_all(self) -> None:
        assert (
            self._dataset is not None
        ), "Dataset not loaded. Provide a dataset directory to the constructor: 'root_dataset_dir'."

        for sample in self._dataset:
            answer = self.infer(sample["text"])
            print(answer)
            print("-" * 100)
