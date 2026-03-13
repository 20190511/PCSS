import os
import re
import json
import asyncio
import aiohttp
import time
from datetime import datetime
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn, 
    TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
)
from rich.table import Table

load_dotenv()
console = Console()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = "deepseek-chat"

PRICE_HIT = 0.028 / 1_000_000
PRICE_MISS = 0.28 / 1_000_000
PRICE_OUT = 0.42 / 1_000_000

class DeepSeekJsonProcessor:
    def __init__(self, input_path="names.json", output_path="results.json", max_concurrency=50, batch_size=20):
        self.input_path = input_path
        self.output_path = output_path
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.batch_size = batch_size
        self.total_usage = {"hit": 0, "miss": 0, "out": 0}
        
        self.system_prompt = (
            "You are an expert in Korean onomastics and romanized name patterns. "
            "Evaluate the probability (0.0 to 1.0) that a given name is of Korean origin. "
            "Western, Japanese, or Chinese names must be scored low or 0.0. "
            "Return ONLY the numerical score. Examples: 'Kim Min-su' -> 1.0, 'Jessica' -> 0.0."
        )

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

    async def process_name(self, session, name):
        async with self.semaphore:
            headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Name: '{name}'"}
                ],
                "temperature": 0.0 
            }

            try:
                async with session.post(BASE_URL, json=payload, headers=headers, timeout=60) as resp:
                    if resp.status != 200: return None
                    result = await resp.json()
                    content = result['choices'][0]['message']['content'].strip()
                    usage = result.get('usage', {})
                    score = self.extract_score(content)

                    return {
                        "name": name, 
                        "score": score,
                        "hit": usage.get('prompt_cache_hit_tokens', 0),
                        "miss": usage.get('prompt_cache_miss_tokens', 0),
                        "out": usage.get('completion_tokens', 0),
                        "updated_at": datetime.now().isoformat()
                    }
            except Exception as e:
                return None
            
    def load_json(self, path):
        if not os.path.exists(path): return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []

    def save_json(self, path, data):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    async def run(self):
        # 1. 파일 로드 및 필터링
        with console.status("[bold yellow]Loading and filtering JSON files..."):
            all_data = self.load_json(self.input_path)
            already_done = self.load_json(self.output_path)
            
            processed_names = {item['name'] for item in already_done if 'score' in item}
            target_items = [item for item in all_data if item['name'] not in processed_names]

        total_targets = len(target_items)
        if total_targets == 0:
            console.print("[bold green]✔ All names already processed in output file.[/]")
            return

        console.print(f"[cyan]Input:[/][white] {len(all_data)}[/] | [green]Remaining:[/][white] {total_targets}[/]")

        final_results = already_done
        current_batch = []

        async with aiohttp.ClientSession() as session:
            with Progress(
                SpinnerColumn(), 
                TextColumn("[bold magenta]{task.description}"), 
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(), 
                console=console
            ) as progress:
                
                task_id = progress.add_task("DeepSeek Re-judging", total=total_targets)
                tasks = [self.process_name(session, item['name']) for item in target_items]
                
                for completed_task in asyncio.as_completed(tasks):
                    res = await completed_task
                    progress.advance(task_id) 

                    if res:
                        self.total_usage['hit'] += res.pop('hit')
                        self.total_usage['miss'] += res.pop('miss')
                        self.total_usage['out'] += res.pop('out')
                        
                        final_results.append(res)
                        current_batch.append(res)

                        if len(current_batch) >= self.batch_size:
                            self.save_json(self.output_path, final_results)
                            current_batch = []
                            
                if current_batch:
                    self.save_json(self.output_path, final_results)

        self.display_summary()

    def display_summary(self):
        total_cost = (self.total_usage['hit']*PRICE_HIT) + (self.total_usage['miss']*PRICE_MISS) + (self.total_usage['out']*PRICE_OUT)
        table = Table(title="DeepSeek API Usage (JSON Mode)", title_style="bold cyan")
        table.add_column("Type"); table.add_column("Tokens", justify="right"); table.add_column("Cost (USD)", style="green")
        table.add_row("Cache Hit", f"{self.total_usage['hit']:,}", f"${self.total_usage['hit']*PRICE_HIT:.6f}")
        table.add_row("Cache Miss", f"{self.total_usage['miss']:,}", f"${self.total_usage['miss']*PRICE_MISS:.6f}")
        table.add_row("Output", f"{self.total_usage['out']:,}", f"${self.total_usage['out']*PRICE_OUT:.6f}")
        table.add_section(); table.add_row("[bold]Total Cost[/]", "-", f"[bold]${total_cost:.4f}[/]")
        console.print("\n", table)

if __name__ == "__main__":
    processor = DeepSeekJsonProcessor(
        input_path="names.json", 
        output_path="results.json",
        max_concurrency=40, 
        batch_size=20
    )
    try:
        asyncio.run(processor.run())
    except KeyboardInterrupt:
        console.print("\n[bold red]Stopped by user. Progress saved.[/]")