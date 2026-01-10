import { HelpCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { MARKER_TYPES } from "@/api/types";

interface ColorLegendDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Color legend dialog explaining marker colors and algorithm meanings.
 */
export function ColorLegendDialog({ open, onOpenChange }: ColorLegendDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Color Legend</DialogTitle>
          <DialogDescription>
            Understanding the colors and markers in the activity plot
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Sleep Markers */}
          <section>
            <h3 className="font-semibold mb-2">Sleep Markers</h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-3">
                <div className="w-4 h-4 bg-purple-500 rounded" />
                <span><strong>{MARKER_TYPES.MAIN_SLEEP}</strong> - Primary sleep period (overnight sleep)</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-4 h-4 bg-purple-300 rounded" />
                <span><strong>{MARKER_TYPES.NAP}</strong> - Daytime nap or secondary sleep</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-1 h-4 bg-purple-600" />
                <span><strong>Onset Line</strong> - Sleep start time</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-1 h-4 bg-purple-400" />
                <span><strong>Offset Line</strong> - Sleep end time (wake time)</span>
              </div>
            </div>
          </section>

          {/* Nonwear Markers */}
          <section>
            <h3 className="font-semibold mb-2">Nonwear Markers</h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-3">
                <div className="w-4 h-4 bg-orange-500 rounded" />
                <span><strong>Manual Nonwear</strong> - User-marked nonwear periods</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-4 h-4 bg-red-500/30 rounded border border-red-500" />
                <span><strong>Choi Nonwear</strong> - Algorithm-detected nonwear (hatched)</span>
              </div>
            </div>
          </section>

          {/* Algorithm Colors */}
          <section>
            <h3 className="font-semibold mb-2">Algorithm Results</h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-3">
                <div className="w-4 h-4 bg-purple-600/40 rounded" />
                <span><strong>Sleep</strong> - Algorithm scored as sleep (low activity)</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-4 h-4 bg-amber-500/40 rounded" />
                <span><strong>Wake</strong> - Algorithm scored as wake (high activity)</span>
              </div>
            </div>
          </section>

          {/* Data Table Colors */}
          <section>
            <h3 className="font-semibold mb-2">Data Table Colors</h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-3">
                <div className="w-4 h-4 bg-purple-500/30 rounded border-l-4 border-purple-600" />
                <span><strong>Current Marker Row</strong> - Selected marker timestamp</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-purple-600">Purple text</span>
                <span>- Sleep scored epochs</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-amber-600">Amber text</span>
                <span>- Wake scored epochs</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-red-600">Red text</span>
                <span>- Choi nonwear detected</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-orange-600">Orange text</span>
                <span>- Manual nonwear overlap</span>
              </div>
            </div>
          </section>

          {/* Keyboard Shortcuts */}
          <section>
            <h3 className="font-semibold mb-2">Keyboard Shortcuts</h3>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div><kbd className="px-1 bg-muted rounded">←</kbd> / <kbd className="px-1 bg-muted rounded">→</kbd></div>
              <div>Navigate dates</div>

              <div><kbd className="px-1 bg-muted rounded">Q</kbd> / <kbd className="px-1 bg-muted rounded">E</kbd></div>
              <div>Move onset left/right</div>

              <div><kbd className="px-1 bg-muted rounded">A</kbd> / <kbd className="px-1 bg-muted rounded">D</kbd></div>
              <div>Move offset left/right</div>

              <div><kbd className="px-1 bg-muted rounded">C</kbd> or <kbd className="px-1 bg-muted rounded">Del</kbd></div>
              <div>Delete selected marker</div>

              <div><kbd className="px-1 bg-muted rounded">Ctrl</kbd>+<kbd className="px-1 bg-muted rounded">4</kbd></div>
              <div>Toggle 24h/48h view</div>

              <div><kbd className="px-1 bg-muted rounded">Ctrl</kbd>+<kbd className="px-1 bg-muted rounded">Shift</kbd>+<kbd className="px-1 bg-muted rounded">C</kbd></div>
              <div>Clear all markers</div>

              <div><kbd className="px-1 bg-muted rounded">Esc</kbd></div>
              <div>Cancel marker creation</div>
            </div>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Button to open the color legend dialog.
 */
export function ColorLegendButton({ onClick }: { onClick: () => void }) {
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={onClick}
      title="Show color legend and keyboard shortcuts"
      data-testid="color-legend-btn"
    >
      <HelpCircle className="h-4 w-4" />
    </Button>
  );
}
