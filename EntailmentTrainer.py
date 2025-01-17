from transformers import Seq2SeqTrainer, AutoTokenizer, AlbertForSequenceClassification
import torch

from RE2.src.evaluator import Evaluator

class EntailmentTrainer(Seq2SeqTrainer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loss_fnct = torch.nn.CrossEntropyLoss()
        self.tokenizer_entail = AutoTokenizer.from_pretrained('textattack/albert-base-v2-snli')
        self.model_entail = AlbertForSequenceClassification.from_pretrained('textattack/albert-base-v2-snli')
        self.device = torch.device("cuda")
        for param in self.model_entail.parameters():
          param.requires_grad = False
        self.model_entail.to(self.device)

        # Evaluator(model_path="textattack/albert-base-v2-snli", data_file=None)

    def compute_loss(self, model, inputs, return_outputs=False):
        # implement entailment scoring here
        # non-differentiable because of model generation? how to handle this?
        # might just work naively?
        loss, outputs = super().compute_loss(model, inputs, return_outputs=True)
        #print(inputs.keys())
        gen_outputs = model.generate(inputs["input_ids"], attention_mask=inputs["attention_mask"], max_length=56)
        gen_outputs = self.tokenizer.batch_decode(gen_outputs, skip_special_tokens=True)
        input_docs = self.tokenizer.batch_decode(inputs["input_ids"], skip_special_tokens=True)

        #print("contradiction score is", self.inference_score([["I am doing well", "I am sick"]]))
        entail_pairs = []
        pair_len = [0]
        for i in range(len(gen_outputs)):
            curr_pairs = [[gen_outputs[i], sent] for sent in input_docs[i].split("\n")]
            entail_pairs.extend(curr_pairs)
            pair_len.append(pair_len[-1] + len(curr_pairs))
        custom_loss = self.inference_score(entail_pairs)
        custom_loss = torch.FloatTensor([1-torch.max(custom_loss[pair_len[i-1]:pair_len[i]]) for i in range(1, len(pair_len))])
        custom_loss = torch.mean(custom_loss)
        #print(custom_loss)

        custom_loss = custom_loss.to('cuda')
        custom_loss += loss.to('cuda')

        return (custom_loss, outputs) if return_outputs else custom_loss


    def inference_score(self, sent_pairs):
        softmax = torch.nn.Softmax(dim=1)
        inputs = self.tokenizer_entail(sent_pairs, return_tensors="pt", padding=True).to(self.device)
        #inputs = [self.tokenizer_entail(datum, return_tensors="pt", padding=True) for datum in sent_pairs]
        outputs = self.model_entail(**inputs)
        logits = outputs.logits
        #return logits[:, 2]
        return softmax(logits)[:, 0]


