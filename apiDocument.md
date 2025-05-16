## Qwen2-VL-OCR2-2B-Instruct

The Qwen2-VL-OCR2-2B-Instruct model is a fine-tuned version of Qwen/Qwen2-VL-2B-Instruct, tailored for tasks that involve Optical Character Recognition (OCR), English language understanding, and math problem solving with LaTeX formatting. This model integrates a conversational approach with visual and textual understanding to handle multi-modal tasks effectively.

### Previous Version

[Qwen2-VL-OCR-2B-Instruct](https://huggingface.co/prithivMLmods/Qwen2-VL-OCR-2B-Instruct)

### Key Enhancements:

* **SoTA understanding of images of various resolution & ratio:** Qwen2-VL achieves state-of-the-art performance on visual understanding benchmarks, including MathVista, DocVQA, RealWorldQA, MTVQA, etc.

* **Understanding videos of 20min+:** Qwen2-VL can understand videos over 20 minutes for high-quality video-based question answering, dialog, content creation, etc.

* **Agent that can operate your mobiles, robots, etc.:** With the abilities of complex reasoning and decision-making, Qwen2-VL can be integrated with devices like mobile phones, robots, etc., for automatic operation based on visual environment and text instructions.

* **Multilingual Support:** To serve global users, besides English and Chinese, Qwen2-VL now supports the understanding of texts in different languages inside images, including most European languages, Japanese, Korean, Arabic, Vietnamese, etc.

### How to Use

```python
from transformers import Qwen2VLForConditionalGeneration, AutoTokenizer, AutoProcessor
from qwen_vl_utils import process_vision_info

# default: Load the model on the available device(s)
model = Qwen2VLForConditionalGeneration.from_pretrained(
    "prithivMLmods/Qwen2-VL-OCR2-2B-Instruct", torch_dtype="auto", device_map="auto"
)

# We recommend enabling flash_attention_2 for better acceleration and memory saving, especially in multi-image and video scenarios.
# model = Qwen2VLForConditionalGeneration.from_pretrained(
#     "prithivMLmods/Qwen2-VL-OCR2-2B-Instruct",
#     torch_dtype=torch.bfloat16,
#     attn_implementation="flash_attention_2",
#     device_map="auto",
# )

# default processor
processor = AutoProcessor.from_pretrained("prithivMLmods/Qwen2-VL-OCR2-2B-Instruct")

# The default range for the number of visual tokens per image in the model is 4-16384.
# You can set min_pixels and max_pixels according to your needs.

messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "image",
                "image": "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen-VL/assets/demo.jpeg",
            },
            {"type": "text", "text": "Describe this image."},
        ],
    }
]

# Preparation for inference
text = processor.apply_chat_template(
    messages, tokenize=False, add_generation_prompt=True
)
image_inputs, video_inputs = process_vision_info(messages)
inputs = processor(
    text=[text],
    images=image_inputs,
    videos=video_inputs,
    padding=True,
    return_tensors="pt",
)
inputs = inputs.to("cuda")

# Inference: Generation of the output
generated_ids = model.generate(**inputs, max_new_tokens=128)
generated_ids_trimmed = [
    out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
]
output_text = processor.batch_decode(
    generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
)
print(output_text)
```

### Buffering Output

```python
buffer = ""
for new_text in streamer:
    buffer += new_text
    # Remove <|im_end|> or similar tokens from the output
    buffer = buffer.replace("<|im_end|>", "")
    yield buffer
```

### Key Features

#### Vision-Language Integration:

* Combines image understanding with natural language processing to convert images into text.

#### Optical Character Recognition (OCR):

* Extracts and processes textual information from images with high accuracy.

#### Math and LaTeX Support:

* Solves math problems and outputs equations in LaTeX format.

#### Conversational Capabilities:

* Designed to handle multi-turn interactions, providing context-aware responses.

#### Image-Text-to-Text Generation:

* Inputs can include images, text, or a combination, and the model generates descriptive or problem-solving text.
