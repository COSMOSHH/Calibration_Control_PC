from __future__ import annotations

from pathlib import Path
from shutil import copy2

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from ..config import OUTPUT_DIR, TEMPLATE_DIR
from ..models import CalibrationResult
from ..utils import format_phase


# Excel 中最佳点用红色字体标记，便于人工核对扫描结果。
RED_FONT = Font(color="FF0000")


class ExcelExporter:
    """负责 UI0 校准数据的 Excel 读写。

    当前输出分三类：
    - Feed1 单馈源功率测试表：TestData_Feed1_BDp30_212.xlsx
    - Feed2~4 相位校准过程表：CalProcess_Feed{n}wrt{ref}_BDp30_212.xlsx
    - 四馈源最终汇总表：CalData_MultiFeed_BDp30_212.xlsx

    调试最佳相位继承时重点看 read_best_feed_point() 和 _write_reference_rows()。
    """

    def __init__(self, template_dir: Path = TEMPLATE_DIR, output_dir: Path = OUTPUT_DIR) -> None:
        self.template_dir = Path(template_dir)
        self.output_dir = Path(output_dir)
        # 输出目录不存在时自动创建，避免首次运行保存失败。
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_scan_result(self, result: CalibrationResult) -> Path:
        """按目标馈源编号选择保存格式。

        Feed1 是单馈源功率测试，Feed2~4 是相对前序馈源的相位校准过程。
        """
        if result.config.target_feed_id == 1:
            return self._save_feed1_test_data(result)
        return self._save_cal_process(result)

    def save_multi_feed_result(self, frequency_ghz: float, beam_angle_deg: float) -> Path:
        """生成四馈源最终汇总表。

        它会依次读取 Feed1~Feed4 已保存过程表中的最佳点；如果某个 Feed
        还没有扫描结果，就抛出异常提醒 UI。
        """
        output = self._copy_or_create("CalData_MultiFeed_BDp30_212.xlsx", "CalData")
        wb = load_workbook(output)
        ws = wb.active
        ws["A1"] = frequency_ghz
        ws["B1"] = beam_angle_deg

        missing: list[int] = []
        for feed_id in range(1, 5):
            best = self.read_best_feed_point(feed_id)
            if best is None:
                missing.append(feed_id)
                continue

            phase_deg, power_uw = best
            # 模板按每个 Feed 占两行排布，实际数据写在 feed_id * 2 + 1 行。
            row = feed_id * 2 + 1
            ws.cell(row=row, column=2, value=phase_deg)
            ws.cell(row=row, column=3, value=round(power_uw, 6))
            self._mark_cells_red(ws, row, (2, 3))

        if missing:
            missing_text = ", ".join(f"Feed{feed_id}" for feed_id in missing)
            raise ValueError(f"缺少最终汇总所需的最佳点数据：{missing_text}")

        wb.save(output)
        return output

    def _save_feed1_test_data(self, result: CalibrationResult) -> Path:
        """保存 Feed1 单馈源功率测试结果。

        从第 3 行开始写：A 列相位，B 列功率(uW)，最大功率点标红。
        """
        output = self._copy_or_create("TestData_Feed1_BDp30_212.xlsx", "TestData")
        wb = load_workbook(output)
        ws = wb.active
        ws["A1"] = result.config.frequency_ghz

        best = result.best_point
        self._clear_rows(ws, start_row=3, max_col=2)
        for row_index, point in enumerate(result.points, start=3):
            ws.cell(row=row_index, column=1, value=point.phase_deg)
            ws.cell(row=row_index, column=2, value=round(point.average_power_uw, 6))
            if point is best:
                self._mark_cells_red(ws, row_index, (1, 2))

        wb.save(output)
        return output

    def _save_cal_process(self, result: CalibrationResult) -> Path:
        """保存 Feed2~4 的相位校准过程表。

        文件名中的 wrt 表示“相对前序馈源”。例如 Feed3wrt12 表示 Feed1/2
        已固定在最佳相位，当前扫描 Feed3。
        """
        ref = "".join(str(feed_id) for feed_id in range(1, result.config.target_feed_id))
        output_name = f"CalProcess_Feed{result.config.target_feed_id}wrt{ref}_BDp30_212.xlsx"
        output = self._copy_or_create(output_name, "CalProcess")

        wb = load_workbook(output)
        ws = wb.active
        ws["A1"] = result.config.frequency_ghz
        ws["B1"] = result.config.beam_angle_deg

        self._write_reference_rows(ws, result.config.target_feed_id)

        # Feed2 从第 5 行开始，Feed3 从第 7 行开始，Feed4 从第 9 行开始。
        data_start_row = result.config.target_feed_id * 2 + 1
        best = result.best_point
        self._clear_data_columns(ws, start_row=data_start_row, columns=(2, 3))
        for row_index, point in enumerate(result.points, start=data_start_row):
            ws.cell(row=row_index, column=2, value=point.phase_deg)
            ws.cell(row=row_index, column=3, value=round(point.average_power_uw, 6))
            if point is best:
                self._mark_cells_red(ws, row_index, (2, 3))

        wb.save(output)
        return output

    def read_best_feed_point(self, feed_id: int) -> tuple[float, float] | None:
        """读取某个馈源历史表中的最佳相位点。

        返回 (phase_deg, power_uw)。UI0 依靠这个函数继承前序最佳相位，
        UI1 的自动校准也会读取这些最佳相位作为偏移。
        """
        workbook = self._output_path_for_feed(feed_id)
        if workbook is None or not workbook.exists():
            return None

        wb = load_workbook(workbook, data_only=True)
        ws = wb.active
        start_row = 3 if feed_id == 1 else feed_id * 2 + 1
        return self._read_best_point(ws, start_row)

    def _write_reference_rows(self, ws: Worksheet, target_feed_id: int) -> None:
        """把前序馈源的最佳点写入当前过程表顶部区域。"""
        for feed_id in range(1, target_feed_id):
            best = self.read_best_feed_point(feed_id)
            if best is None:
                continue
            phase_deg, power_uw = best
            row = feed_id * 2 + 1
            ws.cell(row=row, column=2, value=phase_deg)
            ws.cell(row=row, column=3, value=round(power_uw, 6))
            self._mark_cells_red(ws, row, (2, 3))

    def _read_best_point(self, ws: Worksheet, start_row: int) -> tuple[float, float] | None:
        """从指定起始行往下扫描，选出功率最大的相位点。"""
        best: tuple[float, float] | None = None
        for row in range(start_row, ws.max_row + 1):
            # Feed1 表使用 A/B 列；Feed2~4 过程表使用 B/C 列。
            phase = ws.cell(row=row, column=2 if start_row > 3 else 1).value
            power = ws.cell(row=row, column=3 if start_row > 3 else 2).value
            if not isinstance(phase, (int, float)) or not isinstance(power, (int, float)):
                continue
            if best is None or power > best[1]:
                best = (float(phase), float(power))
        return best

    def _output_path_for_feed(self, feed_id: int) -> Path | None:
        """根据馈源编号定位它对应的输出文件。"""
        if feed_id == 1:
            return self.output_dir / "TestData_Feed1_BDp30_212.xlsx"
        if 2 <= feed_id <= 4:
            ref = "".join(str(current) for current in range(1, feed_id))
            return self.output_dir / f"CalProcess_Feed{feed_id}wrt{ref}_BDp30_212.xlsx"
        return None

    def _copy_or_create(self, output_name: str, sheet_name: str) -> Path:
        """优先从模板复制输出文件；没有模板时创建一个最小工作簿。

        如果 output 已存在但模板缺失，则复用现有输出，避免覆盖用户手工调整过的表。
        """
        output = self.output_dir / output_name
        template = self._template_path(output_name)
        if template.exists():
            copy2(template, output)
            return output
        if output.exists():
            return output

        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name
        wb.save(output)
        return output

    def _template_path(self, output_name: str) -> Path:
        """匹配模板文件名。

        支持两种命名：与输出文件同名，或 stem 后追加 -standard。
        """
        template = self.template_dir / output_name
        if template.exists():
            return template

        output_path = Path(output_name)
        standard_name = f"{output_path.stem}-standard{output_path.suffix}"
        return self.template_dir / standard_name

    def _clear_rows(self, ws, start_row: int, max_col: int) -> None:
        """清空指定起始行之后的连续列，防止旧扫描数据残留。"""
        for row in range(start_row, ws.max_row + 1):
            for col in range(1, max_col + 1):
                ws.cell(row=row, column=col).value = None

    def _clear_data_columns(self, ws: Worksheet, start_row: int, columns: tuple[int, ...]) -> None:
        """只清空过程表中的数据列，保留模板其它说明或公式区域。"""
        for row in range(start_row, ws.max_row + 1):
            for col in columns:
                ws.cell(row=row, column=col).value = None

    def _mark_cells_red(self, ws: Worksheet, row: int, columns: tuple[int, ...]) -> None:
        """把最佳点单元格标红。"""
        for col in columns:
            ws.cell(row=row, column=col).font = RED_FONT

    def describe_scan(self, result: CalibrationResult) -> str:
        """生成简短扫描描述，用于 UI 消息或后续日志扩展。"""
        config = result.config
        return (
            f"Feed{config.target_feed_id} "
            f"{format_phase(config.phase_start_deg)}to{format_phase(config.phase_end_deg)} "
            f"step {format_phase(config.phase_step_deg)}"
        )
