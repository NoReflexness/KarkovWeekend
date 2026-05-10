import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "@/components/ui/button";

describe("Button", () => {
  it("renders its children", () => {
    render(<Button>Klik mig</Button>);
    expect(screen.getByRole("button", { name: "Klik mig" })).toBeInTheDocument();
  });
});
