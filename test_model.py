from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch

BASE_MODEL = "Qwen/Qwen2.5-7B-Instruct"
ADAPTER = "2434addy/qwen2.5-7b-nyayadraft-qlora"

print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

print("Loading model (this will take 5-10 mins on CPU)...")
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=torch.float32,
    device_map="cpu",
)
model = PeftModel.from_pretrained(model, ADAPTER)
model.eval()
print("Model loaded!")

doc_type = "affidavit_general"
details = "Name: Ramesh Kumar, Age: 35, Address: Mumbai. Declaring that he is the sole owner of the property at Plot 12, Andheri West."

messages = [
    {"role": "system", "content": "You are NyayaDraft, an AI assistant that drafts Indian legal documents."},
    {"role": "user", "content": f"Draft a {doc_type.replace('_', ' ')} with the following details: {details}"}
]

text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tokenizer(text, return_tensors="pt")

print("Generating document...")
with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_new_tokens=1024,
        do_sample=False,
        pad_token_id=tokenizer.eos_token_id,
    )

result = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
print("\n--- GENERATED DOCUMENT ---\n")
print(result)
