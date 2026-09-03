// ============================================================
// 后端错误码 → 中文提示
// 后端业务错误 = HTTP 200 + success:false + message 为错误码字符串，
// 这里集中翻译，未知错误码原样返回（通常已是中文或可读文本）。
// ============================================================

export const API_ERROR_MESSAGES: Record<string, string> = {
  CASE_NOT_FOUND: '案件不存在或已被删除',
  REPORT_NOT_FOUND: '判决书尚未生成，请先完成辩论分析',
  MISSING_FIELDS: '案件信息还未收集完整，请先在对话中补充信息',
  HIGH_RISK_DECISION: '该决策超出系统支持范围（如医疗、投资、法律等），无法进行分析',
  CASE_NOT_COMPLETED: '案件尚未判决完成，暂不能提交复盘',
  PARSE_ERROR: '暂时无法理解这条信息，请换个说法试试',
  UNSUPPORTED_CASE_TYPE: '该决策类型暂不支持，请先使用购物决策',
  DEBATE_FAILED: '辩论分析失败，请稍后重试',
  DATABASE_ERROR: '服务端数据异常，请稍后重试',
  INTEGRITY_ERROR: '数据冲突，请刷新后重试',
  INTERNAL_SERVER_ERROR: '服务端开小差了，请稍后重试',
  VALIDATION_ERROR: '提交内容有误，请检查后重试',
  UNAUTHORIZED: '登录已失效，请重新登录',
  USER_NOT_FOUND: '用户不存在，请先注册',
  USER_EXISTS: '该用户 ID 已被注册，请换一个',
  WRONG_PASSWORD: '密码错误，请重试',
  INVALID_CREDENTIALS: '用户 ID 或密码不正确',
};

export function translateApiError(message: string | null | undefined, fallback = '操作失败，请稍后重试'): string {
  if (!message) return fallback;
  return API_ERROR_MESSAGES[message] ?? message;
}
