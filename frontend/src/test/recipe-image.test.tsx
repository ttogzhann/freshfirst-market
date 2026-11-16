import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { RecipeImage } from "@/components/fresh/ui-bits";

const catalog = JSON.parse(
  readFileSync(resolve("../backend/app/data/catalog/manifest.json"), "utf8"),
) as { records: { idMeal: string; strMeal: string; strMealThumb: string }[] };
const fallback = "/recipe-images/fallback.webp";

afterEach(cleanup);

describe("RecipeImage", () => {
  it.each(catalog.records)("uses the local illustration for $strMeal", (recipe) => {
    render(<RecipeImage src={recipe.strMealThumb} alt={recipe.strMeal} />);
    const image = screen.getByRole("img", { name: recipe.strMeal });
    expect(image).toHaveAttribute("src", `/recipe-images/${recipe.idMeal}.webp`);
    expect(image).toHaveAttribute("loading", "lazy");
    expect(image).toBeVisible();
  });

  it.each(["http://example.test/photo.jpg", "https://example.test/photo.jpg", "/photo.webp"])(
    "preserves working photo URLs: %s",
    (src) => {
      render(<RecipeImage src={src} alt="Chocolate Gateau" />);
      const image = screen.getByRole("img", { name: "Chocolate Gateau" });
      expect(image).toHaveAttribute("src", src);
      fireEvent.load(image);
      expect(image).toBeVisible();
      expect(screen.queryByText("C")).not.toBeInTheDocument();
      expect(screen.queryByText("No photo available")).not.toBeInTheDocument();
    },
  );

  it.each([
    "",
    "original-authored://freshfirst/catalog/v1/ff-original-000",
    "original-authored://freshfirst/catalog/v1/ff-original-081",
    "original-authored://freshfirst/catalog/v1/ff-original-018?unexpected=1",
    "original-authored://other/catalog/v1/ff-original-018",
    "javascript:alert(1)",
    "data:image/png;base64,not-an-approved-asset",
  ])("uses a local culinary fallback without requesting an unsupported URL: %s", (src) => {
    render(<RecipeImage src={src} alt="Recipe" />);
    expect(screen.getByRole("img", { name: "Recipe" })).toHaveAttribute("src", fallback);
    expect(screen.queryByText("R")).not.toBeInTheDocument();
  });

  it("falls back once for a broken image and recovers on URL changes", () => {
    const { rerender, container } = render(
      <RecipeImage src="https://example.test/broken.jpg" alt="Recipe" />,
    );
    const broken = screen.getByRole("img", { name: "Recipe" });
    fireEvent.error(broken);
    const replacement = screen.getByRole("img", { name: "Recipe" });
    expect(replacement).toHaveAttribute("src", fallback);
    expect(replacement).toBeVisible();
    fireEvent.error(replacement);
    expect(replacement).not.toBeVisible();
    expect(container.querySelectorAll("img")).toHaveLength(1);
    expect(replacement).toHaveAttribute("src", fallback);

    rerender(<RecipeImage src="https://example.test/repaired.jpg" alt="Recipe" />);
    const repaired = screen.getByRole("img", { name: "Recipe" });
    expect(repaired).toHaveAttribute("src", "https://example.test/repaired.jpg");
    expect(repaired).toBeVisible();
    fireEvent.error(broken);
    fireEvent.error(replacement);
    expect(repaired).toHaveAttribute("src", "https://example.test/repaired.jpg");
    expect(repaired).toBeVisible();
    fireEvent.error(repaired);
    expect(screen.getByRole("img", { name: "Recipe" })).toHaveAttribute("src", fallback);

    rerender(<RecipeImage src="/recipe-images/ff-original-018.webp" alt="Porridge" />);
    const local = screen.getByRole("img", { name: "Porridge" });
    expect(local).toBeVisible();
    fireEvent.error(local);
    expect(screen.getByRole("img", { name: "Porridge" })).toHaveAttribute("src", fallback);
  });
});
