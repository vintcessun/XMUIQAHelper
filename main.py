from playwright.sync_api import sync_playwright
from playwright.sync_api import Locator
import time
import os


REPLY = "教学认真负责，各方面都做得很好。"


class IQAHelper:
    def __init__(self):
        p = sync_playwright()
        self.browser = p.start().chromium.launch(headless=False)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.iqa_list = []
        self.iqa_run = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type: type, exc_val: Exception, exc_tb: Exception):
        """退出时自动调用"""
        print("正在清理环境并关闭浏览器...")
        self.page.close()
        self.context.close()
        self.browser.close()

    def wait_url(self, url: str):
        while True:
            try:
                self.page.wait_for_url(url)
                break
            except:
                pass

    def login(self):
        self.page.bring_to_front()
        self.page.goto("https://iqa.xmu.edu.cn/cas/toUrl")
        print("请进行登录...")
        self.wait_url("https://iqa.xmu.edu.cn/xssy/")
        print("登陆成功")

    def run(self):
        self.login()
        time.sleep(3)
        print("开始自动评教")
        iqa = self.fetch_iqa()
        for i in iqa:
            self.goto_eval_page(i)
            self._eval_all_courses()
        print("评教完成，关闭浏览器")

    def fetch_iqa(self):
        ret: list[int] = []
        self.iqa_list = self.page.locator(".pjlb").locator("li").all()
        self.page.goto("https://iqa.xmu.edu.cn/xssy/")
        self.page.bring_to_front()
        for i in range(len(self.iqa_list)):
            ele = self.iqa_list[i]
            tag = ele.get_attribute("class")
            title: str = ele.locator("div").inner_text()
            if tag and tag == "ended":
                print(f"评教{title}已结束，跳过")
                continue
            print(f"评教{title}已加入待评教列表")
            ret.append(i)
        return ret

    def goto_eval_page(self, i: int):
        self.page.goto("https://iqa.xmu.edu.cn/xssy/")
        self.page.wait_for_timeout(1000)
        self.iqa_run = self.page.locator(".pjlb").locator("li").all()
        self.iqa_run[i].click()
        self.page.wait_for_timeout(3000)
        # 点击评教卡片后进入课程列表页(/pk)。部分版本此处还有"开始评教"按钮，有则点，无则直接进入
        self._click_role_or_text("开始评教", ["开始评教", "开始评价", "进入评教"], per_timeout=3000)
        # 等待课程表格出现
        try:
            self.page.locator("tbody tr").first.wait_for(state="visible", timeout=10000)
        except Exception:
            self._dump_diagnostics("进入评教后未找到课程表格")
            raise RuntimeError("进入评教后未找到课程表格，详见 debug_diag.txt / debug_screenshot.png")
        self.page.wait_for_timeout(1000)

    def get_sections(self):
        rows = self.page.locator("tbody").locator("tr").all()
        return rows

    def _click_role_or_text(self, role_name: str, texts: list, per_timeout: int = 2500):
        """优先按 button role 点击，失败后回退到按文本跨 frame 查找。"""
        try:
            self.page.get_by_role("button", name=role_name).click(timeout=per_timeout)
            print(f"[ok] 点击按钮：{role_name}")
            return True
        except Exception:
            pass
        return self._click_by_text(texts, per_timeout)

    def _click_by_text(self, texts: list, per_timeout: int = 2500):
        """在所有 frame（含 iframe）中按候选文本查找并点击第一个可见匹配元素。"""
        for text in texts:
            for frame in self.page.frames:
                try:
                    loc = frame.locator(f"text={text}").first
                    loc.wait_for(state="visible", timeout=per_timeout)
                    loc.click(timeout=per_timeout)
                    print(f"[ok] 点击：{text}")
                    return True
                except Exception:
                    continue
        return False

    def _dump_diagnostics(self, msg: str):
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            lines = [msg, "", "=== 可交互元素文本（button / a）==="]
            for frame in self.page.frames:
                fname = frame.name or "main"
                try:
                    for sel in ("button", "a"):
                        for el in frame.locator(sel).all():
                            try:
                                t = (el.inner_text() or "").strip()
                                if t:
                                    lines.append(f"[{sel}@{fname}] {t}")
                            except Exception:
                                pass
                except Exception:
                    pass
            with open(os.path.join(base, "debug_diag.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.page.screenshot(path=os.path.join(base, "debug_screenshot.png"), full_page=True)
            print(f"诊断信息已写入 {os.path.join(base, 'debug_diag.txt')} 和 debug_screenshot.png")
        except Exception as e:
            print("诊断导出失败:", e)

    def eval_item(self, row: Locator):
        columns = row.locator("td").all()
        name = columns[0].inner_text()
        action = columns[-1]
        btn = action.locator("a, button").first
        try:
            txt = (btn.inner_text() or "").strip()
        except Exception:
            txt = ""
        if txt == "查看":
            print(f"{name}已评教，跳过")
            return False
        print(f"正在评教{name}")
        btn.click()
        self.page.wait_for_timeout(2000)
        if not self._fill_form():
            self._dump_diagnostics("问卷表单未识别/填写失败")
            raise RuntimeError("问卷表单填写失败，详见 debug_diag.txt / debug_screenshot.png")
        if not self._click_role_or_text("提交", ["提交", "提交评教", "确认提交", "保存并提交"]):
            self._dump_diagnostics("未找到「提交」按钮")
            raise RuntimeError("未找到「提交」按钮，详见 debug_diag.txt / debug_screenshot.png")
        self.page.wait_for_timeout(2000)
        return True

    def _fill_form(self):
        """填写评教问卷：客观分填 满分-0.01，主观题填 REPLY。"""
        try:
            que_page = self.page.locator(".yyjzb")
            que_page.wait_for(state="visible", timeout=8000)
        except Exception:
            return False
        questions_table = que_page.locator("ul.clearfix").all()
        questions: list[Locator] = []
        for table in questions_table:
            questions += table.locator("li").all()
        if not questions:
            return False
        for que in questions:
            text = que.inner_text()
            score_pos = text.find("(分)")
            if score_pos != -1:
                inp = que.locator("input")
                score = text[:score_pos].split(" ")[-1]
                try:
                    score_num = int(score) - 0.01
                except ValueError:
                    continue
                inp.fill(f"{score_num}")
            else:
                inp = que.locator("textarea")
                inp.fill(REPLY)
        return True

    def _ensure_course_list(self):
        """确保当前处在课程列表页(/pk)，必要时回到该页。"""
        try:
            self.page.locator("tbody tr").first.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            pass
        try:
            self.page.goto("https://iqa.xmu.edu.cn/pk", timeout=15000)
            self.page.locator("tbody tr").first.wait_for(state="visible", timeout=10000)
            return True
        except Exception:
            return False

    def _eval_all_courses(self):
        """遍历课程列表，逐门点击"评价"并填写提交，直到全部完成。"""
        for _ in range(30):
            rows = self.get_sections()
            target = None
            for row in rows:
                cols = row.locator("td").all()
                if not cols:
                    continue
                act = cols[-1]
                try:
                    links = act.locator("a, button").all()
                    found = any((el.inner_text() or "").strip() == "评价" for el in links)
                except Exception:
                    found = False
                if found:
                    target = row
                    break
            if target is None:
                print("本评教所有课程已评完")
                break
            self.eval_item(target)
            self._ensure_course_list()
            self.page.wait_for_timeout(1500)


if __name__ == "__main__":
    with IQAHelper() as helper:
        helper.run()
