import { it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { AdvancedOptions } from "./AdvancedOptions";
it("keeps values and active count when collapsed", async () => {
  const user = userEvent.setup();
  function Form() {
    const [value, setValue] = useState("");
    return (
      <AdvancedOptions activeCount={value ? 1 : 0}>
        <label>
          源地址
          <input value={value} onChange={(e) => setValue(e.target.value)} />
        </label>
      </AdvancedOptions>
    );
  }
  render(<Form />);
  await user.click(screen.getByRole("button", { name: /高级参数/ }));
  await user.type(screen.getByLabelText("源地址"), "10.0.0.1");
  await user.click(screen.getByRole("button", { name: /高级参数/ }));
  expect(screen.getByText("已生效 1 项")).toBeTruthy();
  await user.click(screen.getByRole("button", { name: /高级参数/ }));
  expect((screen.getByLabelText("源地址") as HTMLInputElement).value).toBe(
    "10.0.0.1",
  );
});
