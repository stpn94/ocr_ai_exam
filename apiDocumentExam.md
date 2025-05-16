# pip install openai

from openai import OpenAI

client = OpenAI(
		base_url = "https://plynzrnj8aa4u41v.us-east-1.aws.endpoints.huggingface.cloud/v1/",
		api_key = "hf_XXXXX"
	)

chat_completion = client.chat.completions.create(
	model="tgi",
	messages=[
	{
		"role": "user",
		"content": [
			{
				"type": "image_url",
				"image_url": {
					"url": "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/transformers/rabbit.png"
				}
			},
			{
				"type": "text",
				"text": "Describe this image in one sentence."
			}
		]
	}
],
	top_p=None,
	temperature=None,
	max_tokens=150,
	stream=True,
	seed=None,
	stop=None,
	frequency_penalty=None,
	presence_penalty=None
)

for message in chat_completion:
	print(message.choices[0].delta.content, end = "")