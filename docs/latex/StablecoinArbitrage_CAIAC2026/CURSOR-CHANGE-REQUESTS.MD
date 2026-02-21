% General Context for Cursor
For a lenght reference, related work is 1.5 pages long. This is just text so use this as a referecne when you cutdown other sections. The current document is 26 pages including the appendix! Check if we can change the margins for the final result based on the CAIAC formatting regulations.

.cursor folder contains an estimate for how much we should be cutting down. Update it based on what I removed (check the git diff) and also make prioritization for what data should be most pivitol for showing.


Moreover, I anticipate we should move some tables or figures into the Appendix so then we can reference them during our paragraphs. When possible group or shrink figures that are related , and make it a side or grid view to save space. 

Everything including reference page cannot be longer than 12 pages. The appendix can span 4 pages. 16 pages total. The current appendix can be shrunken since we have solid visualization.

The following comments are specific based on the section that I read and commented about. 

% Section 1

Probably still able to compress some of the summiraization. Should add the github repo to the abstract if we can.

% Section 2

Will need to further consolidate Work Related work 
Small summaries but good references. 
We should find a way to not have so many subheadings and instead merge a few of the sections together 

Right now this section is 1.5 pages. And NEEDS to be reduced down to 1 page max. 

% ---Section 3

For Figure 2, we should replace it with figure 3. Remove 2 entirely, and give an exampple of a profitable path within the graph space. This shorten the sections slightly. Make figure 3 smaller when you replace it, it has a lot of white space. 

Any section of the paper that has an Em dash need to be replaced with commas. Or rephrased. It is a blind give away that the text was written by an LLM.


Need to do a full pass so that anything that implis that our A* formnulation or is finidng a cycle needs to be changed so that it is actually a path. No room for error on this. Original works talks about cycles which is fine, but we specfically use paths, but cycles can be created if it leads to profit, which is unlikely though because of market balancing.

Maybe it's worth changing 3.4 demonstrative example to represent the path in figure 3:
Kraken:USDT -> Kucoin: USDT -> Kucoin:USDT
This shows intra and extra system exchanges, and shows that is is a path rather than forcing a cycle example.





% --- Section 4

The heursitic explanations are too detailed and to verbose, should be able to reduce it.
4.3 is pretty simple, it just runs in parallel 
4.4 has way too many words and examples. We do not need to explain the constants we assign, should actually be moved into the appendix matter of fact.

% Section 5 

5.3 got removed. It's slightly redundant because the data could be found within the github results files at recent timestamp. It's okay to reference the repo within the appendix by the way.

% Section 5.5

Figure 4 and Figure 5 should be drawn as smaller

Can remove table 7 since it is redundant with the figure 6 data.

Remove figure 7 since it represents that same as figure 8.


FIGURE REFORMATTING NODE:
"""
Make sure to account how the figures change. So if you remove Figure 2, that means every figure listed here will be shifted down by 1. I do not want you removing the wrong figures. I am naming the figures assuming nothing has changed
""""

We can reduce the cross-exchange vs instra-exchange paths paragh.

When you are explaining the data, I do not need you to be so verbose to be honest. Let the figures show the data, and draw conclusions based by pointing to these figures. This applies to all the sections in results 5. 

For example figure 10 I dont really think adds much to the argument. Also figure 12 has pretty stale data


% Section 5.6 ethics

 This should be reduced at least 50%  and moved to the appendix honestly.


% References

Why is it that only CCXT is the only reference that shows up... Jesus.