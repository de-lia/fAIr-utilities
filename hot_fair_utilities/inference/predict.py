# Standard library imports
import os
import time
from glob import glob
from pathlib import Path

# Third party imports
import numpy as np
from tensorflow import keras

from ..georeferencing import georeference
from ..utils import remove_files
from .utils import open_images, save_mask

BATCH_SIZE = 8
IMAGE_SIZE = 256
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"


# Standard library imports
import concurrent.futures
import math


def process_batch(image_batch, model, prediction_path):
    images = open_images(image_batch)
    images = images.reshape(-1, IMAGE_SIZE, IMAGE_SIZE, 3)

    preds = model.predict(images)
    preds = np.argmax(preds, axis=-1)
    preds = np.expand_dims(preds, axis=-1)
    preds = np.where(preds > 0.5, 1, 0)

    for idx, path in enumerate(image_batch):
        save_mask(
            preds[idx],
            str(f"{prediction_path}/{Path(path).stem}.png"),
        )
    del images
    del preds


def predict(checkpoint_path: str, input_path: str, prediction_path: str) -> None:
    """Predict building footprints for aerial images given a model checkpoint.

    This function reads the model weights from the checkpoint path and outputs
    predictions in GeoTIF format. The input images have to be in PNG format.

    The predicted masks will be georeferenced with EPSG:3857 as CRS.

    Args:
        checkpoint_path: Path where the weights of the model can be found.
        input_path: Path of the directory where the images are stored.
        prediction_path: Path of the directory where the predicted images will go.

    Example::

        predict(
            "model_1_checkpt.tf",
            "data/inputs_v2/4",
            "data/predictions/4"
        )
    """
    start = time.time()

    model = keras.models.load_model(checkpoint_path)
    print(f"It took {time.time()-start} sec to load model")
    start = time.time()

    os.makedirs(prediction_path, exist_ok=True)
    image_paths = glob(f"{input_path}/*.png")
    n_batches = math.ceil(len(image_paths) / BATCH_SIZE)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for i in range(n_batches):
            image_batch = image_paths[BATCH_SIZE * i : BATCH_SIZE * (i + 1)]
            futures.append(
                executor.submit(process_batch, image_batch, model, prediction_path)
            )

        concurrent.futures.wait(futures)
    print(f"It took {time.time()-start} sec for prediction")
    start = time.time()

    georeference(prediction_path, prediction_path, is_mask=True)
    print(f"It took {time.time()-start} sec for Georeference")
    start = time.time()

    remove_files(f"{prediction_path}/*.xml")
    remove_files(f"{prediction_path}/*.png")
