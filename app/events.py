"""事件写入层（D1 待实现）。

需要提供：ensure_session()、log_event()。
约束见 sql/001_init.sql 与四天计划：seq 连续、每个事件独立事务、
args/result 超长截断并标记 truncated。
"""
