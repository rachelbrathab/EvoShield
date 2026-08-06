"use client";

import { Loader2, Trash2 } from "lucide-react";
import { useState } from "react";

import {
  type Repository,
} from "@/lib/repository";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogPopup,
  DialogTitle,
} from "@/components/ui/dialog";

type DeleteRepositoryDialogProps = {
  repository: Repository | null;
  onConfirm: (repository: Repository) => Promise<void>;
  onOpenChange: (open: boolean) => void;
};

export function DeleteRepositoryDialog({
  repository,
  onConfirm,
  onOpenChange,
}: DeleteRepositoryDialogProps) {
  const [deleting, setDeleting] = useState(false);

  // `deleting` resets in the `finally` of handleConfirm; no effect needed.
  async function handleConfirm() {
    if (!repository) return;
    setDeleting(true);
    try {
      await onConfirm(repository);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Dialog open={repository !== null} onOpenChange={onOpenChange}>
      <DialogPopup className="max-w-md">
        <DialogHeader>
          <DialogTitle>Remove repository?</DialogTitle>
          <DialogDescription>
            {repository
              ? `${repository.full_name} will be removed from your EvoShield workspace. The GitHub repository itself is never touched, and you can re-import it later.`
              : ""}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="mt-5">
          <DialogClose render={<Button variant="ghost">Cancel</Button>} />
          <Button
            variant="destructive"
            disabled={deleting}
            onClick={() => void handleConfirm()}
          >
            {deleting ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Trash2 className="size-4" />
            )}
            Remove repository
          </Button>
        </DialogFooter>
      </DialogPopup>
    </Dialog>
  );
}
