"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { axiosInstance } from "@/api/axiosInstance";
import ProtectedRoute from "@/components/ProtectedRoute";
import { UserMenu } from "@/components/UserMenu";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ArrowLeft, Plus, Edit, Trash2, Tags } from "lucide-react";
import { Category, Tag } from "@/models/wallets";

export default function SettingsPage() {
  const router = useRouter();
  const [categories, setCategories] = useState<Category[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Category dialog state
  const [categoryDialogOpen, setCategoryDialogOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<Category | null>(null);
  const [categoryName, setCategoryName] = useState("");
  const [isSavingCategory, setIsSavingCategory] = useState(false);
  const [categoryError, setCategoryError] = useState("");

  // Tag dialog state
  const [tagDialogOpen, setTagDialogOpen] = useState(false);
  const [editingTag, setEditingTag] = useState<Tag | null>(null);
  const [tagName, setTagName] = useState("");
  const [isSavingTag, setIsSavingTag] = useState(false);
  const [tagError, setTagError] = useState("");

  async function fetchCategories() {
    try {
      const response = await axiosInstance.get<Category[]>("wallets/categories/");
      setCategories(response.data);
    } catch (error) {
      console.error("Failed to fetch categories:", error);
    }
  }

  async function fetchTags() {
    try {
      const response = await axiosInstance.get<Tag[]>("wallets/tags/");
      setTags(response.data);
    } catch (error) {
      console.error("Failed to fetch tags:", error);
    }
  }

  async function loadData() {
    setIsLoading(true);
    await Promise.all([fetchCategories(), fetchTags()]);
    setIsLoading(false);
  }

  useEffect(() => {
    loadData();
  }, []);

  function handleAddCategory() {
    setEditingCategory(null);
    setCategoryName("");
    setCategoryError("");
    setCategoryDialogOpen(true);
  }

  function handleEditCategory(category: Category) {
    setEditingCategory(category);
    setCategoryName(category.name);
    setCategoryError("");
    setCategoryDialogOpen(true);
  }

  async function handleDeleteCategory(category: Category) {
    if (!confirm(`Are you sure you want to delete "${category.name}"? This will archive the category.`)) {
      return;
    }

    try {
      await axiosInstance.delete(`wallets/categories/${category.id}/`);
      await fetchCategories();
    } catch (error) {
      console.error("Failed to delete category:", error);
      alert("Failed to delete category. Please try again.");
    }
  }

  async function handleSaveCategory() {
    if (!categoryName.trim()) {
      setCategoryError("Category name is required");
      return;
    }

    setIsSavingCategory(true);
    setCategoryError("");

    try {
      if (editingCategory) {
        await axiosInstance.put(`wallets/categories/${editingCategory.id}/`, {
          name: categoryName.trim(),
        });
      } else {
        await axiosInstance.post("wallets/categories/", {
          name: categoryName.trim(),
        });
      }
      setCategoryDialogOpen(false);
      await fetchCategories();
    } catch (error) {
      console.error("Failed to save category:", error);
      setCategoryError("Failed to save category. Please try again.");
    } finally {
      setIsSavingCategory(false);
    }
  }

  // Tag functions
  function handleAddTag() {
    setEditingTag(null);
    setTagName("");
    setTagError("");
    setTagDialogOpen(true);
  }

  function handleEditTag(tag: Tag) {
    setEditingTag(tag);
    setTagName(tag.name);
    setTagError("");
    setTagDialogOpen(true);
  }

  async function handleDeleteTag(tag: Tag) {
    if (!confirm(`Are you sure you want to delete "${tag.name}"?`)) {
      return;
    }

    try {
      await axiosInstance.delete(`wallets/tags/${tag.id}/`);
      await fetchTags();
    } catch (error) {
      console.error("Failed to delete tag:", error);
      alert("Failed to delete tag. Please try again.");
    }
  }

  async function handleSaveTag() {
    if (!tagName.trim()) {
      setTagError("Tag name is required");
      return;
    }

    setIsSavingTag(true);
    setTagError("");

    try {
      if (editingTag) {
        await axiosInstance.put(`wallets/tags/${editingTag.id}/`, {
          name: tagName.trim(),
        });
      } else {
        await axiosInstance.post("wallets/tags/", {
          name: tagName.trim(),
        });
      }
      setTagDialogOpen(false);
      await fetchTags();
    } catch (error) {
      console.error("Failed to save tag:", error);
      setTagError("Failed to save tag. Please try again.");
    } finally {
      setIsSavingTag(false);
    }
  }

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-4">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => router.push("/dashboard")}
                >
                  <ArrowLeft className="mr-2 h-4 w-4" /> Back to Dashboard
                </Button>
              </div>
              <UserMenu />
            </div>
            <div className="mt-4">
              <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
              <p className="text-sm text-gray-500">Manage your categories and preferences</p>
            </div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="grid gap-6">
            {/* Categories Section */}
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Tags className="h-5 w-5" />
                      Categories
                    </CardTitle>
                    <CardDescription>
                      Manage your transaction categories. Categories are shared across all wallets.
                    </CardDescription>
                  </div>
                  <Button onClick={handleAddCategory}>
                    <Plus className="mr-2 h-4 w-4" />
                    Add Category
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="text-center py-8">
                    <p className="text-gray-500">Loading categories...</p>
                  </div>
                ) : categories.length === 0 ? (
                  <div className="text-center py-8">
                    <Tags className="mx-auto h-12 w-12 text-gray-400" />
                    <h3 className="mt-2 text-sm font-medium text-gray-900">No categories</h3>
                    <p className="mt-1 text-sm text-gray-500">Create categories to organize your transactions.</p>
                    <div className="mt-4">
                      <Button onClick={handleAddCategory}>
                        <Plus className="mr-2 h-4 w-4" />
                        Create Category
                      </Button>
                    </div>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {categories.map((category) => (
                        <TableRow key={category.id}>
                          <TableCell className="font-medium">{category.name}</TableCell>
                          <TableCell className="text-right">
                            <div className="flex justify-end gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleEditCategory(category)}
                              >
                                <Edit className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDeleteCategory(category)}
                              >
                                <Trash2 className="h-4 w-4 text-red-600" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>

            {/* Tags Section */}
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Tags className="h-5 w-5" />
                      Tags
                    </CardTitle>
                    <CardDescription>
                      Manage your transaction tags. Tags allow multiple labels per transaction.
                    </CardDescription>
                  </div>
                  <Button onClick={handleAddTag}>
                    <Plus className="mr-2 h-4 w-4" />
                    Add Tag
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="text-center py-8">
                    <p className="text-gray-500">Loading tags...</p>
                  </div>
                ) : tags.length === 0 ? (
                  <div className="text-center py-8">
                    <Tags className="mx-auto h-12 w-12 text-gray-400" />
                    <h3 className="mt-2 text-sm font-medium text-gray-900">No tags</h3>
                    <p className="mt-1 text-sm text-gray-500">Create tags to label your transactions.</p>
                    <div className="mt-4">
                      <Button onClick={handleAddTag}>
                        <Plus className="mr-2 h-4 w-4" />
                        Create Tag
                      </Button>
                    </div>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {tags.map((tag) => (
                        <TableRow key={tag.id}>
                          <TableCell className="font-medium">{tag.name}</TableCell>
                          <TableCell className="text-right">
                            <div className="flex justify-end gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleEditTag(tag)}
                              >
                                <Edit className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDeleteTag(tag)}
                              >
                                <Trash2 className="h-4 w-4 text-red-600" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>
        </main>
      </div>

      {/* Category Dialog */}
      <Dialog open={categoryDialogOpen} onOpenChange={setCategoryDialogOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>
              {editingCategory ? "Edit Category" : "Add Category"}
            </DialogTitle>
            <DialogDescription>
              {editingCategory
                ? "Update the category name."
                : "Create a new category for your transactions."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="category-name">Name</Label>
              <Input
                id="category-name"
                placeholder="e.g., Groceries, Entertainment"
                value={categoryName}
                onChange={(e) => setCategoryName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    handleSaveCategory();
                  }
                }}
                disabled={isSavingCategory}
              />
            </div>
            {categoryError && (
              <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md">
                {categoryError}
              </div>
            )}
          </div>
          <div className="flex justify-end gap-3">
            <Button
              variant="outline"
              onClick={() => setCategoryDialogOpen(false)}
              disabled={isSavingCategory}
            >
              Cancel
            </Button>
            <Button onClick={handleSaveCategory} disabled={isSavingCategory}>
              {isSavingCategory ? "Saving..." : editingCategory ? "Update" : "Create"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Tag Dialog */}
      <Dialog open={tagDialogOpen} onOpenChange={setTagDialogOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>
              {editingTag ? "Edit Tag" : "Add Tag"}
            </DialogTitle>
            <DialogDescription>
              {editingTag
                ? "Update the tag name."
                : "Create a new tag for your transactions."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="tag-name">Name</Label>
              <Input
                id="tag-name"
                placeholder="e.g., vacation, recurring"
                value={tagName}
                onChange={(e) => setTagName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    handleSaveTag();
                  }
                }}
                disabled={isSavingTag}
              />
            </div>
            {tagError && (
              <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md">
                {tagError}
              </div>
            )}
          </div>
          <div className="flex justify-end gap-3">
            <Button
              variant="outline"
              onClick={() => setTagDialogOpen(false)}
              disabled={isSavingTag}
            >
              Cancel
            </Button>
            <Button onClick={handleSaveTag} disabled={isSavingTag}>
              {isSavingTag ? "Saving..." : editingTag ? "Update" : "Create"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </ProtectedRoute>
  );
}
