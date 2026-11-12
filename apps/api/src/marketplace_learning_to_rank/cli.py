from __future__ import annotations
import json
from pathlib import Path
import typer
from marketplace_learning_to_rank.data.generate import generate
from marketplace_learning_to_rank.data.validate import validate
from marketplace_learning_to_rank.data.build import build_embeddings,build_features
from marketplace_learning_to_rank.training.train import train
from marketplace_learning_to_rank.evaluation.run import evaluate
from marketplace_learning_to_rank.evaluation.benchmark import benchmark
from marketplace_learning_to_rank.retrieval.search import SearchEngine
from marketplace_learning_to_rank.retrieval.smoke_encoder import SmokeEncoder
from marketplace_learning_to_rank.core.models import Provider

app=typer.Typer(help="Marketplace Learning to Rank local marketplace ranking tools")
data=typer.Typer();embeddings=typer.Typer();features=typer.Typer();pipeline=typer.Typer()
app.add_typer(data,name='data');app.add_typer(embeddings,name='embeddings');app.add_typer(features,name='features');app.add_typer(pipeline,name='pipeline')
ROOT=Path(__file__).resolve().parents[4];DATA=ROOT/'data/generated';ART=ROOT/'artifacts';MODEL=ART/'models/ranker.txt'
def save_validation(result):
    path=ART/"data/validation.json";path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2))

@data.command('generate')
def generate_command(seed:int=42,provider_count:int=typer.Option(2400,min=2),query_count:int=typer.Option(2400,min=3),candidate_count:int=typer.Option(80,min=1,max=500),cold_start_fraction:float=typer.Option(.15,min=0,max=.8),label_noise:float=typer.Option(.08,min=0,max=1),category:list[str]|None=typer.Option(None,"--category"),region:list[str]|None=typer.Option(None,"--region")):
    regions=[]
    for value in region or []:
        parts=[x.strip() for x in value.split(',',1)]
        if len(parts)!=2:raise typer.BadParameter("Each --region must be `City, Country`")
        regions.append((parts[0],parts[1]))
    generate(seed,provider_count,query_count,candidate_count,cold_start_fraction,label_noise,DATA,category or None,regions or None)
    result=validate(DATA);save_validation(result);typer.echo(json.dumps(result,indent=2))
@data.command('validate')
def validate_command():
    result=validate(DATA);save_validation(result);typer.echo(json.dumps(result,indent=2))
@embeddings.command('build')
def embeddings_command():typer.echo(json.dumps(build_embeddings(DATA,ART/'embeddings'),indent=2))
@features.command('build')
def features_command():typer.echo(json.dumps(build_features(DATA,ART/'features/features.jsonl'),indent=2))
@app.command('train')
def train_command(smoke_encoder:bool=typer.Option(False,help="Use deterministic non-semantic fixture encoder for CI only")):
    encoder=SearchEngine([Provider.model_validate(x) for x in json.loads((DATA/"providers.json").read_text())],encoder=SmokeEncoder()) if smoke_encoder else None
    typer.echo(json.dumps(train(DATA,MODEL,encoder),indent=2))
@app.command('evaluate')
def evaluate_command(smoke_encoder:bool=typer.Option(False,help="Use deterministic non-semantic fixture encoder for CI only")):
    engine=SearchEngine([Provider.model_validate(x) for x in json.loads((DATA/"providers.json").read_text())],encoder=SmokeEncoder()) if smoke_encoder else None
    typer.echo(json.dumps(evaluate(DATA,MODEL,engine=engine),indent=2))
@app.command('benchmark')
def benchmark_command(iterations:int=100,smoke_encoder:bool=typer.Option(False,help="Use deterministic non-semantic fixture encoder for CI only")):
    engine=SearchEngine([Provider.model_validate(x) for x in json.loads((DATA/"providers.json").read_text())],encoder=SmokeEncoder()) if smoke_encoder else None
    typer.echo(json.dumps(benchmark(DATA,MODEL,ART/'evaluations/benchmark.json',iterations,engine=engine),indent=2))
@app.command('report')
def report_command():
    path=ART/'evaluations/evaluation_metrics.json'
    if not path.exists():raise typer.BadParameter("Run `marketplace_learning_to_rank evaluate` first")
    result=json.loads(path.read_text()); lines=["# Marketplace Learning to Rank synthetic held-out evaluation","","Synthetic relevance labels; not human judgments or booking outcomes.","",f"Test queries: {result['query_count']}","","| Strategy | NDCG@10 | Recall@10 | MRR@10 |","|---|---:|---:|---:|"]
    for name,metrics in result['strategies'].items():lines.append(f"| {name} | {metrics['ndcg@10']['mean']:.4f} | {metrics['recall@10']['mean']:.4f} | {metrics['mrr@10']['mean']:.4f} |")
    out=ART/'evaluations/report.md';out.parent.mkdir(parents=True,exist_ok=True);out.write_text('\n'.join(lines)+'\n');typer.echo(str(out))
@pipeline.command('run')
def pipeline_run(seed:int=42,provider_count:int=typer.Option(2400,min=2,max=5000),query_count:int=typer.Option(2400,min=3,max=5000)):
    generate(seed,provider_count,query_count,80,.15,.08,DATA);typer.echo("1/8 generated data")
    validation=validate(DATA);save_validation(validation);typer.echo(json.dumps(validation,indent=2));typer.echo("2/8 validated data")
    typer.echo(json.dumps(build_embeddings(DATA,ART/'embeddings'),indent=2));typer.echo("3/8 built dense embeddings")
    typer.echo(json.dumps(build_features(DATA,ART/'features/features.jsonl'),indent=2));typer.echo("4/8 built features")
    typer.echo(json.dumps(train(DATA,MODEL),indent=2));typer.echo("5/8 trained LambdaMART")
    typer.echo(json.dumps(evaluate(DATA,MODEL),indent=2));typer.echo("6/8 evaluated held-out queries")
    typer.echo(json.dumps(benchmark(DATA,MODEL,ART/'evaluations/benchmark.json'),indent=2));typer.echo("7/8 benchmarked warm local inference")
    report_command();typer.echo("8/8 exported report")
