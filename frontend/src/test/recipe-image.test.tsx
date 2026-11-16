import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { RecipeImage } from "@/components/fresh/ui-bits";

const catalog = JSON.parse(
  readFileSync(resolve("../backend/app/data/catalog/manifest.json"), "utf8"),
) as {
  catalog_hash: string;
  records: { idMeal: string; strMeal: string; strMealThumb: string }[];
};
const fallback = "/recipe-images/fallback.webp";

afterEach(cleanup);

describe("RecipeImage", () => {
  it("ships each catalog illustration and fallback with matching provenance and integrity", () => {
    const directory = resolve("public/recipe-images");
    const manifest = JSON.parse(readFileSync(resolve(directory, "manifest.json"), "utf8")) as {
      sourceCatalogHash: string;
      assets: {
        id: string;
        title: string;
        file: string;
        sha256: string;
        width: number;
        height: number;
        bytes: number;
      }[];
    };
    expect(manifest.sourceCatalogHash).toBe(catalog.catalog_hash);
    expect(manifest.assets.length).toBeGreaterThanOrEqual(1);
    expect(manifest.assets.some((asset) => asset.id === "fallback")).toBe(true);
    const validIds = new Set([...catalog.records.map((recipe) => recipe.idMeal), "fallback"]);
    for (const asset of manifest.assets) {
      expect(validIds.has(asset.id)).toBe(true);
      expect(asset.file).toBe(`${asset.id}.webp`);
      const bytes = readFileSync(resolve(directory, asset.file));
      expect(bytes.subarray(0, 4).toString()).toBe("RIFF");
      expect(bytes.subarray(8, 12).toString()).toBe("WEBP");
      expect(bytes.length).toBe(asset.bytes);
      expect(createHash("sha256").update(bytes).digest("hex")).toBe(asset.sha256);
      expect(asset.width).toBeGreaterThan(0);
      expect(asset.height).toBeGreaterThan(0);
      if (asset.id !== "fallback") {
        expect(asset.title).toBe(
          catalog.records.find((recipe) => recipe.idMeal === asset.id)?.strMeal,
        );
      }
    }
    expect(new Set(manifest.assets.map((asset) => asset.sha256)).size).toBe(manifest.assets.length);
  });

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
