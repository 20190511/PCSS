import sys
import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.json import JSON
from rich import box

BASE_URL = "https://pcss.knpu.re.kr/api/conf"  # 필요시 수정
console = Console()


# ================== (선택) 생성 템플릿 ==================
# "Conference 생성"도 입력 없이 하려면, 후보가 필요함.
# 여기 리스트에 추가하면, 생성도 번호 선택만으로 가능.
CREATE_TEMPLATES = [
    {
        "name": "CoNEXT",
        "params": ["conext"],
        "kind": "Networks",
        "urls": ["https://dblp.org/db/conf/conext/index.html"],
    },
    {
        "name": "IMC",
        "params": ["imc"],
        "kind": "Networks",
        "urls": ["https://dblp.org/db/conf/imc/index.html"],
    },
]

def _primary_param(doc: dict) -> str:
    return (doc.get("params") or [""])[0]


# ================== CLIENT ==================
class ConferenceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _check(self, r: requests.Response):
        if not r.ok:
            raise RuntimeError(f"{r.status_code}: {r.text}")

    # ---------- API ----------
    def get_kinds(self):
        r = self.session.get(self._url("/kinds"))
        self._check(r)
        return r.json()["kinds"]

    def get_by_kind(self, kind: str):
        r = self.session.get(self._url(f"/by-kind/{kind}"))
        self._check(r)
        return r.json()

    def get_conference(self, param: str):
        r = self.session.get(self._url(f"/{param}"))
        self._check(r)
        return r.json()

    def create_conference(self, payload: dict):
        r = self.session.post(self._url("/"), json=payload)
        self._check(r)

    def delete_conference(self, param: str):
        r = self.session.delete(self._url(f"/{param}"))
        self._check(r)

    # ⚠️ 네 서버 라우트에 맞춰 경로 수정 필요:
    # 네가 작성한 FastAPI 라우트는:
    # POST /{param}/urls
    # DELETE /{param}/urls?url=...
    # 그런데 기존 코드는 /conferences/{param}/urls 로 되어있어서 틀림.
    def add_url(self, param: str, url: str):
        r = self.session.post(self._url(f"/{param}/urls"), json={"url": url})
        self._check(r)

    def delete_url(self, param: str, url: str):
        r = self.session.delete(self._url(f"/{param}/urls"), params={"url": url})
        self._check(r)
    
    def add_param(self, base_param: str, new_param: str):
        r = self.session.post(self._url(f"/{base_param}/params"), json={"param": new_param})
        self._check(r)

    def delete_param(self, base_param: str, del_param: str):
        # DELETE에 body를 보내려면 requests는 request()를 쓰는게 안전
        r = self.session.request("DELETE", self._url(f"/{base_param}/params"), json={"param": del_param})
        self._check(r)


client = ConferenceClient(BASE_URL)


# ================== UI Helpers ==================
def header():
    console.clear()
    console.print(
        Panel(
            "[bold magenta]PCSS Conference Manager[/bold magenta]\n"
            "[dim]MongoDB + FastAPI Admin CLI[/dim]",
            box=box.DOUBLE,
        )
    )


def pause():
    console.print()
    Prompt.ask("엔터를 누르면 계속합니다", default="")

def add_url_flow():
    kinds = client.get_kinds()
    kind = pick_from_table(...)

    docs = client.get_by_kind(kind)
    conf = pick_from_table(...)
    base = _primary_param(conf)
    add_url(base)

def delete_url_flow():
    kinds = client.get_kinds()
    kind = pick_from_table(...)

    docs = client.get_by_kind(kind)
    conf = pick_from_table(...)
    base = _primary_param(conf)
    delete_url(base)


def pick_from_table(title: str, columns: list[str], rows: list[list[str]], item_payloads: list[object]):
    """
    rows: 화면에 보여줄 문자열 리스트(열별)
    item_payloads: 실제 선택 결과로 돌려줄 객체 리스트 (rows와 길이 동일)
    """
    table = Table(title=title, box=box.SIMPLE, show_lines=True)
    table.add_column("번호", justify="right", style="bold")

    for col in columns:
        table.add_column(col)

    for idx, r in enumerate(rows, 1):
        table.add_row(str(idx), *r)

    console.print(table)

    if not item_payloads:
        return None

    choices = [str(i) for i in range(1, len(item_payloads) + 1)]
    choice = Prompt.ask("번호 선택", choices=choices)
    return item_payloads[int(choice) - 1]


# ================== Features (입력 없는 흐름) ==================
def show_kinds():
    kinds = client.get_kinds()
    _ = pick_from_table(
        title="Conference Kinds (조회 전용)",
        columns=["Kind"],
        rows=[[k] for k in kinds],
        item_payloads=kinds,
    )
    # 조회 전용이므로 선택 결과는 사용하지 않아도 됨
    pause()


def show_by_kind():
    kinds = client.get_kinds()
    kind = pick_from_table(
        title="Kind 선택",
        columns=["Kind"],
        rows=[[k] for k in kinds],
        item_payloads=kinds,
    )
    if not kind:
        return

    docs = client.get_by_kind(kind)

    conf = pick_from_table(
        title=f"Conferences in [{kind}] (선택해서 관리)",
        columns=["Name", "Primary Param", "Params(#)", "URLs(#)"],
        rows=[
            [
                d.get("name", ""),
                _primary_param(d) or "-",
                str(len(d.get("params") or [])),
                str(len(d.get("urls") or [])),
            ]
            for d in docs
        ],
        item_payloads=docs,
    )
    if not conf:
        return

    base = _primary_param(conf)
    if not base:
        console.print(Panel("이 conference는 params가 비어있습니다.", border_style="red"))
        pause()
        return

    manage_conference(base)


def show_conference():
    kinds = client.get_kinds()
    kind = pick_from_table(
        title="Kind 선택",
        columns=["Kind"],
        rows=[[k] for k in kinds],
        item_payloads=kinds,
    )
    if not kind:
        return

    docs = client.get_by_kind(kind)
    conf = pick_from_table(
        title=f"Conference 선택 ({kind})",
        columns=["Name", "Primary Param", "Params(#)"],
        rows=[[d.get("name",""), _primary_param(d) or "-", str(len(d.get("params") or []))] for d in docs],
        item_payloads=docs,
    )
    if not conf:
        return

    base = _primary_param(conf)
    doc = client.get_conference(base)
    console.print(Panel(JSON.from_data(doc), title=f"[{base}]", border_style="cyan"))
    pause()


def create_conference():
    # 입력 없는 생성 -> 템플릿 번호 선택으로 생성
    if not CREATE_TEMPLATES:
        console.print(Panel("CREATE_TEMPLATES가 비어있어서 입력 없이 생성할 수 없습니다.", border_style="red"))
        pause()
        return

    payload = pick_from_table(
        title="Conference 생성 (템플릿 선택)",
        columns=["Name", "Param", "Kind", "URLs(count)"],
        rows=[[t["name"], (t.get("params") or ["-"])[0], t["kind"], str(len(t.get("urls", [])))] for t in CREATE_TEMPLATES],
        item_payloads=CREATE_TEMPLATES,
    )
    if not payload:
        return

    # 생성 전 미리보기
    console.print(Panel(JSON.from_data(payload), title="생성할 데이터", border_style="magenta"))
    if Confirm.ask("이대로 생성할까요?", default=False):
        client.create_conference(payload)
        console.print("[bold green]Conference created[/bold green]")
    pause()


def delete_conference():
    # direct param 입력 제거 -> kind -> conf 선택 -> 삭제
    kinds = client.get_kinds()
    kind = pick_from_table(
        title="Kind 선택",
        columns=["Kind"],
        rows=[[k] for k in kinds],
        item_payloads=kinds,
    )
    if not kind:
        return

    docs = client.get_by_kind(kind)
    conf = pick_from_table(
        title=f"삭제할 Conference 선택 ({kind})",
        columns=["Name", "Param"],
        rows=[[d.get("name",""), _primary_param(d) or "-"] for d in docs],
        item_payloads=docs,
    )
    if not conf:
        return

    param = conf["param"]
    console.print(Panel(JSON.from_data(conf), title="삭제 대상", border_style="red"))
    if Confirm.ask(f"[red]{param}[/red] 삭제?", default=False):
        client.delete_conference(param)
        console.print("[bold red]Deleted[/bold red]")
    pause()


def add_url(base_param: str):
    url = Prompt.ask("추가할 URL 입력").strip()
    if not url:
        console.print(Panel("URL이 비어있습니다.", border_style="red"))
        pause()
        return
    if not (url.startswith("http://") or url.startswith("https://")):
        console.print(Panel("URL은 http:// 또는 https:// 로 시작해야 합니다.", border_style="red"))
        pause()
        return

    client.add_url(base_param, url)
    console.print(f"[bold green]URL added[/bold green] -> {base_param} : {url}")
    pause()


def delete_url(base_param: str):
    full = client.get_conference(base_param)
    urls = full.get("urls", [])
    if not urls:
        console.print(Panel("삭제할 URL이 없습니다.", border_style="yellow"))
        pause()
        return

    url = pick_from_table(
        title=f"삭제할 URL 선택 ({base_param})",
        columns=["URL"],
        rows=[[u] for u in urls],
        item_payloads=urls,
    )
    if not url:
        return

    console.print(Panel(f"[red]{url}[/red]\n삭제할까요?", title="확인", border_style="red"))
    if Confirm.ask("삭제?", default=False):
        client.delete_url(base_param, url)
        console.print("[bold red]URL deleted[/bold red]")
    pause()

def add_param(base_param: str):
    new_param = Prompt.ask("추가할 param 입력 (예: conext2025)").strip()
    if not new_param:
        console.print(Panel("param이 비어있습니다.", border_style="red"))
        pause()
        return
    client.add_param(base_param, new_param)
    console.print(f"[bold green]Param added[/bold green] -> {base_param} + {new_param}")
    pause()


def delete_param(base_param: str):
    doc = client.get_conference(base_param)
    params = doc.get("params") or []
    if len(params) <= 1:
        console.print(Panel("params가 1개뿐이라 삭제할 수 없습니다.", border_style="yellow"))
        pause()
        return

    # base_param(대표)도 포함해서 목록에서 선택
    target = pick_from_table(
        title=f"삭제할 param 선택 ({base_param})",
        columns=["param"],
        rows=[[p] for p in params],
        item_payloads=params,
    )
    if not target:
        return

    console.print(Panel(f"[red]{target}[/red]\n삭제할까요?", title="확인", border_style="red"))
    if Confirm.ask("삭제?", default=False):
        client.delete_param(base_param, target)
        console.print("[bold red]Param deleted[/bold red]")
    pause()


def manage_conference(base_param: str):
    while True:
        doc = client.get_conference(base_param)

        header()
        console.print(Panel(JSON.from_data(doc), title=f"현재 Conference ({base_param})", border_style="cyan"))

        table = Table(title="Conference 관리", box=box.SIMPLE, show_lines=True)
        table.add_column("번호", justify="right")
        table.add_column("기능", style="cyan")

        table.add_row("1", "URL 추가")
        table.add_row("2", "URL 삭제")
        table.add_row("3", "param 추가")
        table.add_row("4", "param 삭제")
        table.add_row("5", "Conference 삭제")
        table.add_row("0", "뒤로")

        console.print(table)

        choice = Prompt.ask("선택", choices=["0", "1", "2", "3", "4", "5"])
        if choice == "0":
            return
        elif choice == "1":
            add_url(base_param)
        elif choice == "2":
            delete_url(base_param)
        elif choice == "3":
            add_param(base_param)
        elif choice == "4":
            delete_param(base_param)
        elif choice == "5":
            console.print(Panel("삭제 메뉴로 이동합니다.", border_style="yellow"))
            pause()
            client.delete_conference(base_param)
            console.print("[bold red]Deleted[/bold red]")
            pause()
            return


# ================== MENU ==================
MENU = {
    "1": ("Kind 목록 보기", show_kinds),
    "2": ("Kind별 Conference 조회/관리", show_by_kind),
    "3": ("Conference 단일 조회", show_conference),
    "4": ("Conference 생성(템플릿 선택)", create_conference),
    "5": ("Conference 삭제(선택)", delete_conference),
    "6": ("Conference URL 추가(후보 선택)", add_url_flow),
    "7": ("Conference URL 삭제(목록 선택)", delete_url_flow),
    "0": ("종료", None),
}


def main():
    while True:
        header()

        table = Table(title="메뉴", box=box.SIMPLE, show_lines=True)
        table.add_column("번호", justify="right")
        table.add_column("기능", style="cyan")
        for k, (label, _) in MENU.items():
            table.add_row(k, label)
        console.print(table)

        choice = Prompt.ask("선택", choices=list(MENU.keys()))
        if choice == "0":
            console.print("[bold]Bye[/bold]")
            sys.exit(0)

        _, action = MENU[choice]
        try:
            console.clear()
            action()
        except Exception as e:
            console.print(Panel(str(e), title="[red]ERROR[/red]", border_style="red"))
            pause()


if __name__ == "__main__":
    main()
