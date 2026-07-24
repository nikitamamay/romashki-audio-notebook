
# Romashki Audio Notebook

<img src="assets/gui.png" alt="Application GUI" style="max-width: 100%">

A simple GUI for [whisper.cpp](https://github.com/ggml-org/whisper.cpp) speech recognition model.

In order for the application to work, you need to download audio recognition model data file in GGML format, for example, `ggml-small.bin`. Refer to [instructions](https://github.com/ggml-org/whisper.cpp/tree/master/models) or download from [Hugging Face](https://huggingface.co/ggerganov/whisper.cpp). Note: do not use `*.en` data files in order to support multiple languages. When Romashki Audio Notebook is launched, you need to specify the paths to `whisper-cli` executable and to the model file in the application settings.
