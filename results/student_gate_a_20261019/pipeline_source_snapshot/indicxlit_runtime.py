"""Local inference with official IndicXlit v1.0 indic-en weights, via PyTorch.

Fairseq's six-layer pre-norm transformer is mapped strictly onto torch.nn layers.
This avoids installing incompatible old Fairseq dependencies into the app's Python
environment. All learned tensors must be consumed; no weights are trained here.
Decoding is greedy, without optional English word-frequency rescoring. Outputs
remain machine Romanizations requiring Gate-A review, not human transliterations.
"""
import argparse
import json
import math
from pathlib import Path
import random
import re
import unicodedata
import zipfile

import torch
from torch import nn
from .contract import sha, write_json

WORD = re.compile(r"[\u0c80-\u0ce5\u0cf0-\u0cff]+")

def native_normalize(text):
    return unicodedata.normalize("NFC",text).replace("\u200c","").replace("\u200d","")

class IndicXlit(nn.Module):
    def __init__(self, folder, device="cpu"):
        super().__init__()
        self.folder=Path(folder);self.device_name=device
        with torch.serialization.safe_globals([argparse.Namespace]):
            checkpoint=torch.load(self.folder/"transformer/indicxlit.pt",map_location="cpu",weights_only=True)
        cfg=vars(checkpoint["cfg"]["model"]);state=checkpoint["model"]
        expected=dict(encoder_embed_dim=256,decoder_embed_dim=256,encoder_layers=6,decoder_layers=6,
            encoder_attention_heads=4,decoder_attention_heads=4,encoder_ffn_embed_dim=1024,decoder_ffn_embed_dim=1024,
            encoder_normalize_before=True,decoder_normalize_before=True,activation_fn="gelu",
            no_scale_embedding=False,layernorm_embedding=True,encoder_learned_pos=False,decoder_learned_pos=False)
        for key,value in expected.items():
            if cfg.get(key)!=value:raise ValueError(f"Unsupported checkpoint configuration {key}: {cfg.get(key)}")
        with zipfile.ZipFile(self.folder/'ai4bharat_transliteration-1.1.3-py3-none-any.whl') as wheel:
            langs=wheel.read('ai4bharat/transliteration/transformer/models/indic2en/lang_list.txt').decode().split()
        def symbols(lang):
            words=['<s>','<pad>','</s>','<unk>']
            words.extend(line.rsplit(' ',1)[0] for line in (self.folder/f'corpus-bin/dict.{lang}.txt').read_text(encoding='utf-8').splitlines())
            words.extend('__'+lang+'__' for lang in langs)
            return words
        self.src_symbols=symbols('kn');self.tgt_symbols=symbols('en')
        self.src_index={c:i for i,c in enumerate(self.src_symbols)}
        if len(self.src_symbols)!=state['encoder.embed_tokens.weight'].shape[0] or len(self.tgt_symbols)!=state['decoder.embed_tokens.weight'].shape[0]:
            raise ValueError('Language-tag order or dictionaries do not match the checkpoint')
        self.src_embed=nn.Embedding(len(self.src_symbols),256,padding_idx=1)
        self.tgt_embed=nn.Embedding(len(self.tgt_symbols),256,padding_idx=1)
        self.src_norm=nn.LayerNorm(256);self.tgt_norm=nn.LayerNorm(256)
        self.encoder=nn.TransformerEncoder(nn.TransformerEncoderLayer(256,4,1024,0.,'gelu',batch_first=True,norm_first=True),6,norm=nn.LayerNorm(256),enable_nested_tensor=False)
        self.decoder=nn.TransformerDecoder(nn.TransformerDecoderLayer(256,4,1024,0.,'gelu',batch_first=True,norm_first=True),6,norm=nn.LayerNorm(256))
        self.output=nn.Linear(256,len(self.tgt_symbols),bias=False)
        mapped={};used=set()
        def take(old,new):mapped[new]=state[old];used.add(old)
        for old,new in [('encoder.embed_tokens.weight','src_embed.weight'),('decoder.embed_tokens.weight','tgt_embed.weight'),('decoder.output_projection.weight','output.weight')]:take(old,new)
        for old,new in [('encoder.layernorm_embedding','src_norm'),('decoder.layernorm_embedding','tgt_norm'),('encoder.layer_norm','encoder.norm'),('decoder.layer_norm','decoder.norm')]:
            for suffix in ('weight','bias'):take(old+'.'+suffix,new+'.'+suffix)
        for side in ('encoder','decoder'):
            for i in range(6):
                pre=f'{side}.layers.{i}.'
                attns=[('self_attn','self_attn')]+([('encoder_attn','multihead_attn')] if side=='decoder' else [])
                for old,new in attns:
                    for suffix in ('weight','bias'):
                        keys=[pre+old+'.'+p+'_proj.'+suffix for p in ('q','k','v')]
                        mapped[pre+new+'.in_proj_'+suffix]=torch.cat([state[k] for k in keys]);used.update(keys)
                        take(pre+old+'.out_proj.'+suffix,pre+new+'.out_proj.'+suffix)
                norms=[('self_attn_layer_norm','norm1'),('final_layer_norm','norm2' if side=='encoder' else 'norm3')]
                if side=='decoder':norms.append(('encoder_attn_layer_norm','norm2'))
                for old,new in norms+[('fc1','linear1'),('fc2','linear2')]:
                    for suffix in ('weight','bias'):take(pre+old+'.'+suffix,pre+new+'.'+suffix)
        ignored={k for k in state if k.endswith('.version') or k.endswith('embed_positions._float_tensor')}
        if set(state)-used-ignored:raise ValueError('Unmapped learned parameters: '+str(set(state)-used-ignored))
        self.load_state_dict(mapped,strict=True)
        self.eval().to(device)
        torch.backends.mha.set_fastpath_enabled(False)
        self.model_config={**expected,'decoding':'greedy','beam':1,'rescore':False,'seed':42,'device':device,
            'checkpoint_sha256':sha(self.folder/'transformer/indicxlit.pt'),'language_order':langs,
            'mapped_learned_tensors':len(used),'unmapped_learned_tensors':0,'torch':torch.__version__}

    def positions(self,tokens):
        mask=tokens.ne(1).long();positions=torch.cumsum(mask,dim=1)*mask+1
        frequencies=torch.exp(torch.arange(128,device=tokens.device,dtype=torch.float32)*(-math.log(10000)/127))
        angles=positions.unsqueeze(-1)*frequencies
        embeddings=torch.cat([angles.sin(),angles.cos()],dim=-1)
        return embeddings*mask.unsqueeze(-1)

    @torch.inference_mode()
    def words(self,words,max_output=60):
        encoded=[[self.src_index['__kn__']]+[self.src_index.get(c,3) for c in native_normalize(word)]+[2] for word in words]
        length=max(map(len,encoded));tokens=torch.full((len(words),length),1,device=self.device_name,dtype=torch.long)
        for i,values in enumerate(encoded):tokens[i,:len(values)]=torch.tensor(values,device=self.device_name)
        padding=tokens.eq(1)
        x=self.src_norm(self.src_embed(tokens)*16+self.positions(tokens))
        x=x.masked_fill(padding.unsqueeze(-1),0)
        memory=self.encoder(x,src_key_padding_mask=padding)
        output=torch.full((len(words),1),2,device=self.device_name,dtype=torch.long)
        finished=torch.zeros(len(words),device=self.device_name,dtype=torch.bool)
        scores=torch.zeros(len(words),device=self.device_name)
        lengths=torch.zeros(len(words),device=self.device_name)
        allowed=[2]+[i for i,c in enumerate(self.tgt_symbols) if re.fullmatch('[a-z]',c)]
        invalid=[i for i in range(len(self.tgt_symbols)) if i not in allowed]
        for step in range(max_output):
            y=self.tgt_norm(self.tgt_embed(output)*16+self.positions(output))
            causal=torch.triu(torch.ones(output.shape[1],output.shape[1],device=self.device_name,dtype=torch.bool),1)
            decoded=self.decoder(y,memory,tgt_mask=causal,memory_key_padding_mask=padding)
            logits=self.output(decoded[:,-1]);logits[:,invalid]=-torch.inf
            if step==0:logits[:,2]=-torch.inf
            probs=logits.log_softmax(-1);selected=probs.argmax(-1)
            active=~finished;scores+=probs.gather(1,selected[:,None]).squeeze(1)*active;lengths+=active
            selected=torch.where(finished,torch.full_like(selected,2),selected)
            output=torch.cat([output,selected[:,None]],dim=1);finished|=selected.eq(2)
            if bool(finished.all()):break
        result=[]
        for word,seq,score,n,ids,done in zip(words,output[:,1:].cpu().tolist(),scores.cpu().tolist(),lengths.cpu().tolist(),encoded,finished.cpu().tolist()):
            chars=[]
            for symbol in seq:
                if symbol==2:break
                chars.append(self.tgt_symbols[symbol])
            result.append({'native':word,'romanized':''.join(chars),'mean_log_probability':round(score/max(n,1),5),
                'input_unknown_characters':3 in ids,'completed':done,'method':'IndicXlit_v1_indic_en_pytorch_greedy'})
        return result

def romanize_text(text,cache):
    text=native_normalize(text)
    return WORD.sub(lambda m:cache[m.group()]['romanized'],text)

def run_cache(args):
    import pyarrow.parquet as pq
    import csv
    args.out.parent.mkdir(parents=True, exist_ok=True)
    random.seed(42);torch.manual_seed(42);torch.cuda.manual_seed_all(42)
    torch.set_num_threads(4)
    texts=[]
    with Path('data/trusted/conversational_bpcc.csv').open(encoding='utf-8-sig',newline='') as stream:
        texts.extend(r['kannada_script'] for r in csv.DictReader(stream))
    texts.extend(pq.read_table('data/raw/in22_conv/in22_conv_mteb_default_test.parquet',columns=['kan_Knda'])['kan_Knda'].to_pylist())
    words=sorted({w for text in texts for w in WORD.findall(native_normalize(text))},key=lambda w:(len(w),w))
    cache={}
    if args.out.exists():
        for line in args.out.read_text(encoding='utf-8').splitlines():
            r=json.loads(line);cache[r['native']]=r
    model=IndicXlit(args.model,'cuda' if torch.cuda.is_available() and not args.cpu else 'cpu')
    write_json(args.out.with_suffix('.config.json'),model.model_config)
    missing=[w for w in words if w not in cache]
    with args.out.open('a',encoding='utf-8',newline='\n') as stream:
        for start in range(0,len(missing),args.batch_size):
            result=model.words(missing[start:start+args.batch_size])
            for row in result:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
            stream.flush()
            if start%(args.batch_size*10)==0:print(json.dumps({'romanized':len(cache)+start+len(result),'total':len(words)}),flush=True)
    print(json.dumps({'cache':str(args.out),'words':len(words),'sha256':sha(args.out)}),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',type=Path,default=Path('models/indicxlit_v1'))
    p.add_argument('--out',type=Path,required=True);p.add_argument('--batch-size',type=int,default=64);p.add_argument('--cpu',action='store_true')
    run_cache(p.parse_args())

if __name__=='__main__':main()
