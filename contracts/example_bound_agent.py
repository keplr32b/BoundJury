# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *

try:
    _UserError = gl.vm.UserError
except Exception:
    _UserError = Exception


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise _UserError(msg)


class ExampleBoundAgent(gl.Contract):
    boundjury_addr: Address
    action_id: str
    acts: u256

    def __init__(self, boundjury_addr: str, action_id: str):
        addr = (boundjury_addr or "").strip()
        require(len(addr) > 0, "boundjury_addr required")
        if not addr.startswith("0x") and not addr.startswith("0X"):
            addr = "0x" + addr
        self.boundjury_addr = Address(addr)
        aid = (action_id or "").strip()
        require(1 <= len(aid) <= 64, "bad action_id")
        self.action_id = aid
        self.acts = u256(0)

    def _ensure_in_bound(self) -> None:
        bj = gl.get_contract_at(self.boundjury_addr)
        out = bj.view().is_out_of_bound(self.action_id)
        require(out is not True, "action out of bound by BoundJury")

    @gl.public.write
    def act(self) -> str:
        self._ensure_in_bound()
        self.acts = self.acts + u256(1)
        return "ok"

    @gl.public.write
    def withdraw(self) -> str:
        self._ensure_in_bound()
        return "withdraw_ok"

    @gl.public.view
    def status(self) -> str:
        bj = gl.get_contract_at(self.boundjury_addr)
        out = bj.view().is_out_of_bound(self.action_id)
        if out is True:
            return "BLOCKED"
        return "ACTIVE"

    @gl.public.view
    def get_action_id(self) -> str:
        return self.action_id

    @gl.public.view
    def get_boundjury(self) -> Address:
        return self.boundjury_addr

    @gl.public.view
    def get_acts(self) -> u256:
        return self.acts