using Vintagestory.API.Common;
using Vintagestory.GameContent;

namespace Lampwright;

/// <summary>
/// The Wearable behaviour, with one change: a belt that has no condition yet starts at
/// full condition instead of a random one.
///
/// Vanilla's CollectibleBehaviorWearable.ensureConditionExists rolls
/// Rand.NextDouble() * 0.4 - a random 0-40% - the first time it meets a clothing stack
/// carrying no "condition" attribute, and only OnCreatedByCrafting sets 1. That is the
/// right call for vanilla, where clothing without a condition is loot, a trader's
/// stock or something pulled from creative. It is the wrong call for this belt, which
/// is crafted and then dyed: a barrel recipe clones its output and writes it into the
/// slot without going through OnCreatedByCrafting, so the dyed belt arrives with no
/// condition attribute and vanilla rolls it a fresh, random, usually bad one. A belt
/// that went into the barrel at 100% could come out Heavily Tattered.
///
/// Overriding the roll fixes that at the source and is cheaper than patching the
/// barrel: no Harmony, no reaching into vanilla recipe internals. It also fixes the
/// same surprise for /giveitem and the creative inventory, which is where this was
/// first noticed - a belt handed out in creative was born at 16%.
///
/// The trade-off is that re-dyeing refurbishes the belt rather than preserving its
/// wear. That is the generous reading, and it costs a litre of dye and four sealed
/// hours. Wear from here on is ordinary: it ticks down as clothing does and takes a
/// sewing kit (+75%), cloth or linen (+50%) or flax twine (+10%) to put back.
/// </summary>
public class LampbeltWearable : CollectibleBehaviorWearable
{
	public LampbeltWearable(CollectibleObject collObj) : base(collObj)
	{
	}

	protected override void ensureConditionExists(ItemSlot slot, bool markdirty = true)
	{
		// Same guards as vanilla: a DummySlot is a throwaway used for lookups, and a
		// garment with no warmth is outside the condition system altogether. The side
		// check vanilla makes is dropped - it only exists to keep the two sides from
		// rolling different random numbers, and there is no random number here.
		if (slot is DummySlot || slot.Itemstack == null) return;
		if (slot.Itemstack.Attributes.HasAttribute("condition")) return;
		if (GetMaxWarmth(slot) == 0f) return;

		slot.Itemstack.Attributes.SetFloat("condition", 1f);
		if (markdirty) slot.MarkDirty();
	}
}
