import { useCallback, useEffect, useRef } from "react";
import { Modal } from "antd";
import { useBlocker, useBeforeUnload } from "react-router-dom";
import { useResourceContext } from "../app/context";
export function useDraftGuard(dirty: boolean, busy: boolean) {
  const { registerGuard } = useResourceContext();
  const [modal, holder] = Modal.useModal();
  const bypass = useRef(false);
  const confirm = useCallback(() => {
    if (bypass.current || !dirty) return Promise.resolve(true);
    if (busy) {
      modal.info({ title: "请求正在提交，请等待返回后再切换。" });
      return Promise.resolve(false);
    }
    return new Promise<boolean>((resolve) => {
      modal.confirm({
        title: "放弃尚未提交的分析条件？",
        content: "切换后表单将清空，已提交的后台任务不受影响。",
        okText: "放弃并切换",
        cancelText: "继续填写",
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      });
    });
  }, [dirty, busy, modal]);
  useEffect(() => registerGuard(confirm), [registerGuard, confirm]);
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      !bypass.current &&
      dirty &&
      (currentLocation.pathname !== nextLocation.pathname ||
        currentLocation.search !== nextLocation.search),
  );
  const showing = useRef(false);
  useEffect(() => {
    if (blocker.state !== "blocked") {
      showing.current = false;
      return;
    }
    if (showing.current) return;
    showing.current = true;
    void confirm().then((allowed) =>
      allowed ? blocker.proceed() : blocker.reset(),
    );
  }, [blocker, confirm]);
  useBeforeUnload(
    useCallback(
      (event) => {
        if (dirty && !bypass.current) {
          event.preventDefault();
          event.returnValue = "";
        }
      },
      [dirty],
    ),
  );
  return {
    holder,
    allowNavigation: () => {
      bypass.current = true;
    },
  };
}
