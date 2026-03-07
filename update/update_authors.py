import os
import re
import asyncio
import aiohttp
import json
from datetime import datetime
from typing import List
from dotenv import load_dotenv
from pymongo import UpdateOne, IndexModel, ASCENDING
from rich.console import Console
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn, 
    TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
)
from rich.table import Table
from app.db import name_col, papers_col

load_dotenv()
console = Console()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = "deepseek-chat"

PRICE_HIT = 0.028 / 1_000_000
PRICE_MISS = 0.28 / 1_000_000
PRICE_OUT = 0.42 / 1_000_000

class DeepSeekNameProcessor:
    def __init__(self, max_concurrency=150, batch_update_size=500):
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.batch_update_size = batch_update_size
        self.total_usage = {"hit": 0, "miss": 0, "out": 0}
        
        self.system_prompt = (
            "You are an expert in Korean onomastics and romanized name patterns. "
            "Evaluate the probability (0.0 to 1.0) that a given name is of Korean origin. "
            "Criteria: 1-syllable surname and 2-syllable given names are typical. "
            "Western, Japanese, or Chinese names must be scored low or 0.0. "
            "Return ONLY the numerical score. Examples: 'Kim Min-su' -> 1.0, 'Jessica' -> 0.0."
        )
        self.user_prompt_template = "Name: '{name}'"

    def extract_score(self, content):
        if not content: return None
        match = re.search(r"(\d*\.\d+|\d+)", content)
        if match:
            try:
                val = float(match.group(1))
                if 1.0 < val <= 100.0: val /= 100.0
                return max(0.0, min(1.0, val))
            except: return None
        return None

    async def process_name(self, session, name, progress, task_id):
        async with self.semaphore:
            headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": self.user_prompt_template.format(name=name)}
                ],
            }

            try:
                async with session.post(BASE_URL, json=payload, headers=headers, timeout=60) as resp:
                    if resp.status != 200: return None
                    result = await resp.json()
                    content = result['choices'][0]['message']['content'].strip()
                    usage = result.get('usage', {})
                    score = self.extract_score(content)

                    hit = usage.get('prompt_cache_hit_tokens', 0)
                    cache_status = "[bold green]HIT [/]" if hit > 0 else "[dim]MISS[/]"
                    progress.console.print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] "
                        f"[cyan]{name:<12}[/] | Score: [bold yellow]{score if score is not None else 'FAIL':<5}[/] | {cache_status}"
                    )

                    progress.advance(task_id)
                    return {
                        "name": name, "score": score,
                        "hit": hit,
                        "miss": usage.get('prompt_cache_miss_tokens', 0),
                        "out": usage.get('completion_tokens', 0)
                    }
            except: return None

    async def run_processing(self, target_names: List[str]):
        total_names = len(target_names)
        if total_names == 0:
            console.print("[green]No names to process.[/]")
            return

        db_ops = []
        async with aiohttp.ClientSession() as session:
            with Progress(
                SpinnerColumn(), 
                TextColumn("[bold blue]{task.description}"), 
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("({task.completed}/{task.total})"),
                TimeElapsedColumn(), 
                TimeRemainingColumn(), 
                console=console
            ) as progress:
                
                task_id = progress.add_task("Processing", total=total_names)
                name_iterator = iter(target_names)
                pending = set()

                try:
                    while len(pending) < self.semaphore._value:
                        try:
                            name = next(name_iterator)
                            pending.add(asyncio.create_task(self.process_name(session, name, progress, task_id)))
                        except StopIteration: break

                    while pending:
                        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                        
                        for task in done:
                            res = await task
                            if res and res['score'] is not None:
                                self.total_usage['hit'] += res['hit']
                                self.total_usage['miss'] += res['miss']
                                self.total_usage['out'] += res['out']
                                
                                db_ops.append(UpdateOne(
                                    {"name": res['name']},
                                    {"$set": {"score": res['score'], "updated_at": datetime.now()},
                                     "$setOnInsert": {"created_at": datetime.now()}},
                                    upsert=True
                                ))

                                if len(db_ops) >= self.batch_update_size:
                                    name_col.bulk_write(db_ops)
                                    db_ops = []

                        while len(pending) < self.semaphore._value:
                            try:
                                name = next(name_iterator)
                                pending.add(asyncio.create_task(self.process_name(session, name, progress, task_id)))
                            except StopIteration: break

                except KeyboardInterrupt:
                    console.print("\n[bold red]Interrupted. Saving current progress...[/]")
                finally:
                    if db_ops:
                        name_col.bulk_write(db_ops)
                        console.print(f"[bold green]Batch updated {len(db_ops)} records safely.[/]")

        self.display_summary()

    def display_summary(self):
        total_cost = (self.total_usage['hit']*PRICE_HIT) + (self.total_usage['miss']*PRICE_MISS) + (self.total_usage['out']*PRICE_OUT)
        table = Table(title="Usage Summary", title_style="bold magenta")
        table.add_column("Type"); table.add_column("Tokens", justify="right"); table.add_column("Cost (USD)", style="green")
        table.add_row("Cache Hit", f"{self.total_usage['hit']:,}", f"${self.total_usage['hit']*PRICE_HIT:.6f}")
        table.add_row("Cache Miss", f"{self.total_usage['miss']:,}", f"${self.total_usage['miss']*PRICE_MISS:.6f}")
        table.add_row("Output", f"{self.total_usage['out']:,}", f"${self.total_usage['out']*PRICE_OUT:.6f}")
        table.add_section(); table.add_row("[bold]Total Cost[/]", "-", f"[bold]${total_cost:.4f}[/]")
        console.print("\n", table)

# --- 유틸리티 및 실행 함수 ---

def extract_new_names() -> List[str]:
    with console.status("[bold yellow]Optimizing DB query..."):
        name_col.create_index([("name", ASCENDING)])
        papers_col.create_index([("author_names", ASCENDING)])

    with console.status("[bold yellow]Fetching unique names from papers..."):
        pipeline = [
            {"$unwind": "$author_names"},
            {"$group": {"_id": "$author_names"}}
        ]
        raw_author_names = [doc["_id"] for doc in papers_col.aggregate(pipeline)]

    with console.status("[bold yellow]Cleaning and deduplicating..."):
        cleaned_names = {
            re.sub(r"\d+", "", (name or "")).strip()
            for name in raw_author_names
            if name
        }
        cleaned_names.discard("")

    with console.status("[bold yellow]Comparing with existing records..."):
        processed_pipeline = [{"$group": {"_id": "$name"}}]
        processed_names = {doc["_id"] for doc in name_col.aggregate(processed_pipeline)}

    update_targets = list(cleaned_names - processed_names)
    console.print(f"[green]Found {len(update_targets)} new names to process.[/]")
    return update_targets

async def rejudge_high_score_names(threshold: float = 0.7):
    """특정 점수 이상의 이름들을 다시 판정"""
    with console.status(f"[bold yellow]Filtering names with score >= {threshold}..."):
        targets = [doc['name'] for doc in name_col.find({"score": {"$gte": threshold}}, {"_id": 0, "name": 1})]
    
    if not targets:
        console.print("[yellow]No targets found for rejudging.[/]")
        return

    console.print(f"[cyan]Starting rejudge for {len(targets)} names...[/]")
    processor = DeepSeekNameProcessor(max_concurrency=50, batch_update_size=50)
    await processor.run_processing(targets)

async def main(automatic=False): # automatic 인자 추가
    processor = DeepSeekNameProcessor(max_concurrency=50, batch_update_size=50)

    if automatic:
        # 스케줄러에 의해 실행될 때는 자동으로 1번 로직 수행
        targets = extract_new_names()
        await processor.run_processing(targets)
        return

    # 직접 실행할 때만 input()을 받음
    choice = input("1: Main Extraction & Process\n2: Rejudge (High Score Only)\nSelect (1/2): ")
    if choice == "1":
        targets = extract_new_names()
        await processor.run_processing(targets)
    elif choice == "2":
        t_input = input("Threshold (default 0.7): ")
        threshold = float(t_input) if t_input else 0.7
        targets = get_rejudge_targets(threshold)
        await processor.run_processing(targets)

if __name__ == "__main__":
    try:
        asyncio.run(main()) # 직접 실행 시 automatic=False
    except KeyboardInterrupt:
        pass