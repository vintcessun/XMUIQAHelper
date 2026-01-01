from playwright.sync_api import sync_playwright
from playwright.sync_api import Locator
import time


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
            state = True
            while state:
                rows = self.get_sections()
                state = state and self.eval_item(rows[0])
                self.page.reload(wait_until="networkidle")
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
        time.sleep(2)
        self.iqa_run = self.page.locator(".pjlb").locator("li").all()
        self.iqa_run[i].click()
        time.sleep(7)
        self.page.get_by_role("button", name="开始评教").click()
        time.sleep(2)

    def get_sections(self):
        rows = self.page.locator("tbody").locator("tr").all()
        return rows

    def eval_item(self, row: Locator):
        columns = row.locator("td").all()
        name = columns[0].inner_text()
        print(f"正在评教{name}")
        button = columns[-1].locator("a")
        if button.inner_text() == "查看":
            print(f"{name}已评教，跳过")
            return False
        button.click()
        time.sleep(2)
        que_page = self.page.locator(".yyjzb")
        questions_table = que_page.locator("ul.clearfix").all()
        questions: list[Locator] = []
        for table in questions_table:
            questions += table.locator("li").all()
        for que in questions:
            text = que.inner_text()
            score_pos = text.find("(分)")
            if score_pos != -1:
                input = que.locator("input")
                score = text[:score_pos].split(" ")[-1]
                score_num = int(score) - 0.01
                input.fill(f"{score_num}")
            else:
                input = que.locator("textarea")
                input.fill(REPLY)
        self.page.get_by_role("button", name="提交").click()
        time.sleep(2)
        return True


if __name__ == "__main__":
    with IQAHelper() as helper:
        helper.run()
